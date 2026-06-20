# NEXUS — Low-Level Design (LLD)

**Document:** Low-Level Design (LLD)  
**Author:** Aditya Shrivastava  
**Version:** 0.1 · Draft  
**Companions:** [HLD](HLD.md) · [Implementation Guide](implementation.md)

---

## Contents

1. [Introduction & Conventions](#1-introduction--conventions)
2. [Data Models & Enumerations](#2-data-models--enumerations)
3. [Persistence Schemas](#3-persistence-schemas)
4. [Ingestion Pipeline](#4-ingestion-pipeline)
5. [Embedding Subsystem](#5-embedding-subsystem)
6. [Retrieval Engine & Algorithms](#6-retrieval-engine--algorithms)
7. [Anti-RAG Router](#7-anti-rag-router)
8. [Knowledge Graph & Entity Resolution](#8-knowledge-graph--entity-resolution)
9. [Memory Subsystem](#9-memory-subsystem)
10. [Governance Internals](#10-governance-internals)
11. [Agent Interface](#11-agent-interface)
12. [Sequence Flows](#12-sequence-flows)
13. [Evaluation Framework](#13-evaluation-framework)
14. [Consistency, Latency & Scale](#14-consistency-latency--scale)
15. [Threat Model](#15-threat-model)
16. [Error Handling & Edge Cases](#16-error-handling--edge-cases)

---

## 1. Introduction & Conventions

This LLD specifies the internals of every component named in the [HLD](HLD.md). It is written to be implementable directly: each subsystem lists its data structures, the algorithm in pseudocode, and its public interface (method contracts). Code is illustrative Python-flavoured pseudocode.

| Convention | Meaning |
|---|---|
| `Model` | A validated data object (Pydantic v2 in the implementation). |
| `→` | "returns" / "flows to" in signatures and flows. |
| **interface** | A public method contract other components depend on. |
| Big-O notes | Given per algorithm where relevant to scale. |

---

## 2. Data Models & Enumerations

Everything stored or moved through NEXUS is one of these typed models. `KnowledgeChunk` is the atomic unit.

### 2.1 Enumerations

```python
class SensitivityLevel(Enum):   PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED   # ordered
class DataDomain(Enum):        CUSTOMER, PRODUCT, MARKETING, ENGINEERING, OPERATIONS, COMPLIANCE, SPORTS, FINANCE
class MemoryTier(Enum):        WORKING, EPISODIC, SEMANTIC, PROCEDURAL
class RetrievalStrategy(Enum): DENSE, SPARSE, HYBRID, GRAPH, DIRECT, STRUCTURED, CACHED
class ChunkingStrategy(Enum):  RECURSIVE, SEMANTIC, SENTENCE, FIXED
class EntityType(Enum):        PLAYER, TEAM, LEAGUE, EVENT, MARKET, PRODUCT, CUSTOMER, EMPLOYEE, POLICY, REGULATION, JURISDICTION, SERVICE
```

### 2.2 KnowledgeChunk — the atomic unit

| Field | Type | Purpose |
|---|---|---|
| `id` | str (uuid) | Primary key |
| `content` | str | The chunk text |
| `domain` | DataDomain | Drives governance + graph linking |
| `sensitivity` | SensitivityLevel | ABAC enforcement key |
| `source_uri` | str | Origin (e.g. `s3://docs/x.pdf#p4`) for lineage |
| `collection` | str | Vector-store namespace |
| `embedding` | float[] \| null | Dense vector |
| `entity_refs` | str[] | KG entity IDs mentioned in this chunk |
| `metadata` | dict | Arbitrary tags (jurisdiction, author, date…) |
| `provenance_id` | str \| null | Link to its ProvenanceRecord |
| `checksum` | str | SHA-256 of content for dedup |
| `token_count` | int | For context-budget accounting |

### 2.3 Graph models

```python
class Entity:
    id, name, entity_type, canonical_name, aliases[], domain,
    properties{}, confidence: float,           # entity-resolution confidence
    source_chunks[],                            # chunks that mention this entity
    embedding: float[] | None                   # for similarity-based resolution

class Relationship:
    id, source_entity_id, target_entity_id, relation_type, weight: float,
    properties{}, bidirectional: bool,
    valid_from, valid_until                      # temporal validity for time-bounded facts
```

### 2.4 Memory, retrieval & governance models

```python
class MemoryTrace:  id, agent_id, session_id, turn_index, role, content,
                    retrieved_chunks[], tool_calls[], timestamp, tier, compressed_into

class RetrievalResult:  chunk: KnowledgeChunk, score: float, strategy: RetrievalStrategy,
                        explanation: str, hop_path: str[] | None

class RetrievalRequest:  query, agent_id, session_id, collections[]|None,
                         strategy, top_k, min_score, sensitivity_cap, include_graph

class AccessClaim:  principal_id, principal_type, domains[], max_sensitivity,
                    collections[], expires_at, attributes{}    # ABAC attributes

class ProvenanceRecord:  id, entity_id, entity_type, activity, agent,
                         used[], generated[], timestamp, metadata{}   # PROV-O shape

class AgentContext:  agent_id, session_id, working_memory[], retrieved_knowledge[],
                     active_entities[], token_budget, used_tokens, retrieval_strategy_used
```

---

## 3. Persistence Schemas

Per HLD principle P4, the relational metadata store is the system of record; the vector index and graph are rebuildable projections.

### Relational store (SQLite prototype → managed RDBMS in prod)

```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY, content TEXT, domain TEXT, sensitivity TEXT,
    source_uri TEXT, collection TEXT, metadata JSON, checksum TEXT,
    provenance_id TEXT, created_at TS, updated_at TS,
    UNIQUE(checksum)                              -- idempotent ingestion / dedup
);
CREATE TABLE episodes (                          -- episodic memory
    id TEXT PRIMARY KEY, agent_id TEXT, session_id TEXT, turn_index INT,
    role TEXT, content TEXT, retrieved_chunks JSON, timestamp TS,
    compressed_into TEXT NULL                     -- chunk id of summary; NULL = not yet compressed
);
CREATE INDEX ix_episodes_agent ON episodes(agent_id, turn_index);
CREATE TABLE provenance (
    id TEXT PRIMARY KEY, entity_id TEXT, entity_type TEXT, activity TEXT,
    agent TEXT, used JSON, generated JSON, timestamp TS, metadata JSON
);
CREATE TABLE audit_log (                         -- append-only; never UPDATE/DELETE
    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TS, principal_id TEXT,
    query_hash TEXT, strategy TEXT, returned_ids JSON,
    excluded_count INT, exclude_reasons JSON
);
```

### Vector store layout

One logical index per `collection`. Each record: `{chunk_id, embedding[], collection, model_id}`. Records carry their embedding `model_id` so cross-collection results can be normalised before fusion.

### Graph store layout

Directed property graph. Nodes keyed by canonical entity ID; edges typed and weighted with temporal validity. Adjacency stored as lists for sparse, BFS-friendly traversal.

---

## 4. Ingestion Pipeline

```
Source ─▶ Extract ─▶ Chunk ─▶ Tag(domain,sensitivity,collection) ─▶ PII-scan
       ─▶ Embed ─▶ Entity-link(KG) ─▶ Provenance ─▶ Store(metadata+vector+graph)
```

### 4.1 Chunking strategy selection

| Content type | Strategy | Target size | Overlap | Why |
|---|---|---|---|---|
| General docs | `RECURSIVE` | 512 tok | 20% | Paragraph-aware; balances context vs precision |
| Dense knowledge | `SEMANTIC` | variable | 0% | Embedding boundaries; no artificial splits |
| Legal / regulatory | `SENTENCE` | 3–5 sent | 1 sent | Preserves legal precision |
| Code / structured | `FIXED` | 256 tok | 0% | Structure > semantic continuity |

### 4.2 Deduplication

Exact dedup via SHA-256 checksum (DB UNIQUE constraint → idempotent re-ingestion). Near-duplicate detection via embedding cosine ≥ 0.97 at ingest → versioned, not overwritten.

### 4.3 Interface

```
IngestionPipeline.ingest(source: Source, claims: AccessClaim) → list[KnowledgeChunk]
```
Runs the full pipeline; raises `AccessError` if the principal may not ingest into the target collection. Idempotent on checksum.

---

## 5. Embedding Subsystem

> **No model lock-in.** All embedding access goes through one interface. The prototype uses a local model, falling back to a pure-Python hashing/TF-IDF vectoriser so the demo runs with zero installs. Production swaps in a hosted or fine-tuned model — callers don't change.

```
Embedder.encode(text: str) → float[]
```
Returns an L2-normalised dense vector. Batched variant `encode_many(texts)` for ingestion throughput.

```
Embedder.model_id → str
```
Identifies the model so collections record which space their vectors live in.

### HyDE (short-query expansion)

When a query has < 8 tokens, optionally generate a hypothetical answer with the LLM and embed *that* — it is a closer proxy to target documents than the bare question.

---

## 6. Retrieval Engine & Algorithms

Three independent retrievers produce ranked candidate lists; Reciprocal Rank Fusion merges them; governance filters the result.

### 6.1 Sparse — BM25

```python
# Okapi BM25. Inverted index maps term → posting list. O(query_terms × postings).
def bm25_score(query, doc, idf, avgdl, k1=1.5, b=0.75):
    score = 0
    for term in query:
        f = freq(term, doc)
        score += idf[term] * (f*(k1+1)) / (f + k1*(1 - b + b*len(doc)/avgdl))
    return score
```

### 6.2 Dense — ANN cosine

Query embedded once; nearest neighbours by cosine. Production uses an HNSW index (≈O(log n)); prototype uses brute-force cosine (O(n)) which is fine at demo scale.

### 6.3 Graph RAG — multi-hop

```python
def graph_rag(query, max_hops=3, degree_cap=8):
    seeds   = [kg.resolve(e) for e in extract_entities(query)]
    visited = bfs(seeds, max_hops, degree_cap)        # cap fan-out to top-N edges by weight
    chunks  = flatten(e.source_chunks for e in visited)
    return [(c, proximity_score(hop_distance[c])) for c in chunks]
```

Degree cap + hop cap prevent combinatorial blow-up on high-degree nodes (see §14).

### 6.4 Fusion — Reciprocal Rank Fusion

```python
# Rank-based, parameter-free, robust to incomparable score scales.
def rrf(ranked_lists, k=60):
    scores = defaultdict(float)
    for lst in ranked_lists:                  # [dense, sparse, graph]
        for rank, chunk_id in enumerate(lst):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

**Why RRF over weighted average:** no per-query weight tuning, no score normalisation, no labeled data needed to start — yet competitive with tuned weighted sums on standard benchmarks.

#### Example RRF merge

| BM25 (sparse) | Dense (vector) | Graph (multi-hop) | Fused result |
|---|---|---|---|
| #1 NJ Reg | #1 Boost Policy | #1 NFL MVP | **Boost Policy** (appeared across all 3) |
| #2 Boost Policy | #2 NJ Reg | #2 Boost Policy | **NJ Reg** |
| #3 RG Limits | #3 OddsBoost | #3 NJ Reg | **NFL MVP** |
| #4 MVP Market | #4 RG Limits | #4 OddsBoost | **RG Limits** |

Score formula per chunk: `Σ 1 / (k + rank)` across all lists, k = 60.

### 6.5 Reranking (production)

A cross-encoder re-scores only the post-fusion top-20 as (query, chunk) pairs. Expensive, so bounded to the shortlist; skippable under load.

### 6.6 Interface

```
HybridRetriever.search(req: RetrievalRequest, claims: AccessClaim) → list[RetrievalResult]
```
Routes (§7), runs the enabled retrievers, fuses by RRF, applies governance (§10), returns governed, ranked results with per-result strategy + explanation.

---

## 7. Anti-RAG Router

Routing decides *whether* and *how* to retrieve. Skipping retrieval where it would hurt is the cheapest quality win in the system.

| Route | Trigger signal | Action |
|---|---|---|
| `DIRECT` | General knowledge / math / formatting | Skip retrieval; LLM answers directly |
| `STRUCTURED` | "current", "live", "balance", "odds now" | Route to API/SQL, not the vector store |
| `CACHED` | Semantic cache hit (cos ≥ 0.97) | Return cached result; skip all retrieval |
| `GRAPH` | Multiple named entities / relational question | Graph-first traversal |
| `HYBRID` | Document/policy reasoning (default) | Full sparse+dense+graph → RRF |

```python
def classify(query) -> RetrievalStrategy:
    if semantic_cache.hit(query):            return CACHED
    if has_temporal_or_live_signal(query):   return STRUCTURED
    if is_general_knowledge(query):          return DIRECT
    if entity_count(query) >= 2:             return GRAPH
    return HYBRID                            # safe default
```

Prototype = rule engine; production = fine-tuned classifier, evaluated by router accuracy (§13).

---

## 8. Knowledge Graph & Entity Resolution

### 8.1 Entity resolution

```python
# Map a surface form ("P. Mahomes") to a canonical entity. Confidence-gated.
def resolve(name) -> (Entity, confidence):
    if exact_canonical_match(name):       return e, 1.00
    if alias_table.get(name):             return e, 0.95
    if levenshtein_match(name, max=2):    return e, 0.80
    if embedding_cosine(name) >= 0.92:    return e, 0.75
    return new_entity(name), 0.0          # <0.7 ⇒ create + flag, never auto-merge
```

### 8.2 Traversal & temporal edges

BFS with hop + degree caps (§6.3, §14). Edges carry `valid_from / valid_until`; traversal filters to edges valid at query time unless a point-in-time is given.

### 8.3 Ontology

```
PLAYER ──PLAYS_FOR──▶ TEAM ──COMPETES_IN──▶ LEAGUE
EVENT  ──HAS_MARKET──▶ MARKET ──GOVERNED_BY──▶ POLICY ──APPLIES_IN──▶ JURISDICTION
PRODUCT ──REGULATED_BY──▶ REGULATION
ENTITY ──DESCRIBED_BY──▶ CHUNK
```

#### Sample graph entities

| Entity | Type | Key properties |
|---|---|---|
| P. Mahomes | PLAYER | position: QB, status: active |
| KC Chiefs | TEAM | city: Kansas City |
| NFL | LEAGUE | sport: Football |
| NFL Season | EVENT | status: in-progress |
| NFL MVP | MARKET | type: futures |
| Boost Policy | POLICY | version: v4 |
| New Jersey | JURISDICTION | compliance: high |
| NJ Reg 2026 | REGULATION | body: NJ ABC |
| OddsBoost | PRODUCT | version: 3.2 |

#### BFS example — 2 hops from "P. Mahomes"

```
P. Mahomes
  ├─ PLAYS_FOR ──▶ KC Chiefs
  │                  └─ COMPETES_IN ──▶ NFL
  ├─ PARTICIPATES_IN ──▶ NFL Season
  │                        └─ HAS_MARKET ──▶ NFL MVP
  └─ DESCRIBED_BY ──▶ Sports doc (chunk)
```

Entities reachable (2 hops): KC Chiefs, NFL, NFL Season, NFL MVP, Sports doc — all included in the agent's context window.

### 8.4 Interface

```
KnowledgeGraph.upsert_entity(e)
KnowledgeGraph.upsert_relationship(r)
KnowledgeGraph.resolve(name) → (Entity, confidence)
KnowledgeGraph.neighbors(id, hops, degree_cap) → Set[Entity]
```

---

## 9. Memory Subsystem

| Tier | Structure | Eviction | Latency |
|---|---|---|---|
| **Working** | Bounded deque (~10 turns / token budget) | FIFO → demote to Episodic | O(1) |
| **Episodic** | SQLite `episodes` | Compress > N turns → Semantic | ~1ms |
| **Semantic** | Vector store + KG | Versioned; never hard-deleted | ~50–200ms |
| **Procedural** | In-memory registry | Manual version bump | O(1) |

### Memory tier behaviour (example with cap=4, compress@6)

```
Turn 1  → Working: [T1]
Turn 2  → Working: [T1, T2]
Turn 3  → Working: [T1, T2, T3]
Turn 4  → Working: [T1, T2, T3, T4]
Turn 5  → Working full → T1 demoted to Episodic: [T2,T3,T4,T5] | Episodic: [T1]
Turn 6  → T2 demoted: Working [T3,T4,T5,T6] | Episodic: [T1,T2]
...
Turn 10 → Episodic hits 6 → compress T1–T6 into Semantic summary; Episodic cleared
```

**Compression is explicit and reversible.** Traces are marked `compressed_into`, never deleted — so "what was actually said" is always recoverable for audit.

### 9.1 Episodic compression

```python
def compress(agent_id):
    traces  = uncompressed_traces(agent_id)           # > N (default 20)
    summary = llm_summarize(traces) or extractive_fallback(traces)
    chunk   = KnowledgeChunk(content=summary, collection="episodic_summaries", ...)
    semantic.store(chunk)
    provenance.record(activity="episodic_compression", used=trace_ids, generated=[chunk.id])
    mark_compressed(trace_ids, into=chunk.id)          # UPDATE, never DELETE — full audit trail
```

### 9.2 Memory Manager interface

```
MemoryManager.acquire(trace: MemoryTrace) → None
  Push to working + episodic; trigger compression if threshold crossed.

MemoryManager.retrieve(req: RetrievalRequest, claims) → list[RetrievalResult]
  Delegates to the retrieval engine.

MemoryManager.compile_context(agent_id, session_id, results) → AgentContext
  Assembles working memory + governed results + active entities into a token-budgeted context window.
```

---

## 10. Governance Internals

### 10.1 ABAC evaluation (fail-closed)

```python
def permits(claim: AccessClaim, c: KnowledgeChunk) -> bool:
    if level(c.sensitivity) > level(claim.max_sensitivity): return False
    if c.domain not in claim.domains:                       return False
    if claim.collections and c.collection not in claim.collections: return False
    if not attributes_match(claim.attributes, c.metadata):  return False  # e.g. jurisdiction
    return True
# Excluded chunks are dropped silently — never error — so error text can't leak their existence.
```

### 10.2 Provenance (PROV-O)

Every chunk/entity/summary links to a `ProvenanceRecord` capturing *activity*, *agent*, *used* (inputs) and *generated* (outputs) — forming a lineage DAG walkable backward from any artifact to its source.

### 10.3 Audit log

Append-only. Every retrieval logs principal, hashed query, strategy, returned IDs, and how many chunks were excluded and why (category, not content). Never updated or deleted.

### 10.4 PII classifier

Runs per chunk at ingestion (regex + model). A hit escalates sensitivity to `RESTRICTED` and raises a compliance flag requiring approval before the chunk joins a shared collection.

---

## 11. Agent Interface

A new agent is a small subclass; the memory lifecycle is inherited. The LLM is isolated behind one method.

```python
class BaseAgent(ABC):
    def think(self, user_input) -> str:
        self.memory.acquire(MemoryTrace(role="user", content=user_input, ...))
        results = self.memory.retrieve(RetrievalRequest(query=user_input, ...), self.claims)
        ctx     = self.memory.compile_context(self.agent_id, self.session_id, results)
        answer  = self._call_llm(ctx.context_string(), user_input)      # subclass / model seam
        self.memory.acquire(MemoryTrace(role="assistant", content=answer, ...))
        return answer

    @abstractmethod
    def _call_llm(self, context: str, query: str) -> str: ...
```

### Lifecycle hooks

| Hook | Trigger | Action |
|---|---|---|
| `on_eviction` | Working memory overflow | Demote trace to episodic |
| `on_compression` | Episodic > threshold | Summarise → semantic; audit |
| `on_session_end` | Session closes | Flush working memory; write session summary |
| `on_forget` | Governed deletion | Mark deleted + audit; never hard-delete |

---

## 12. Sequence Flows

### 12.1 Query turn

```
Agent        MemoryManager     Router      Retriever    Governance     Stores
  │ think(q)      │                │            │            │             │
  ├──acquire─────▶│ store working+episodic      │            │             │
  ├──retrieve────▶│──classify(q)──▶│            │            │             │
  │               │◀──strategy─────┤            │            │             │
  │               │──search(q)──────────────────▶│ sparse+dense+graph─────▶│
  │               │               │            │◀──candidates────────────┤
  │               │               │            │──RRF fuse                │
  │               │               │            │──filter(claims)─────────▶│ ABAC
  │               │◀──governed results──────────┤            │             │
  ├──compile_context──▶ build AgentContext      │            │             │
  │◀──context─────┤                │            │            │             │
  ├──_call_llm──▶ answer grounded in context    │            │             │
  └──acquire(assistant) ; audit_log.append      │            │             │
```

### 12.2 Ingestion

```
Source ─▶ Extract ─▶ Chunk ─▶ Tag/PII ─▶ Embed ─▶ Link(KG)
                                                       │
   metadata.insert (TXN + outbox) ◀── Provenance ◀─────┘
                                                       └─▶ vector.upsert ; graph.upsert (async, idempotent)
```

---

## 13. Evaluation Framework

> **You cannot ship retrieval you cannot measure.** The eval harness is a Day-1 CI gate, not a late-stage task — a retrieval system without it degrades silently.

| Layer | Metrics | Catches |
|---|---|---|
| Component retrieval | recall@k, precision@k, MRR, nDCG@k | Right chunk not retrieved / ranked too low |
| End-to-end generation | faithfulness, answer relevance, context precision/recall | Hallucination; "right docs, wrong answer" |
| Router | routing accuracy (confusion matrix) | Wrong strategy chosen for query intent |

### Golden set bootstrap

LLM-generated (chunk → questions) → human-validated subset → production-mined from real feedback → adversarial edge cases. New chunking/embedding/retrieval changes must pass the suite in CI; new strategies run in production shadow mode before promotion.

---

## 14. Consistency, Latency & Scale

### 14.1 Multi-store consistency

The relational metadata store is the single system of record; vector + graph are derived projections. Ingestion writes the source-of-truth row plus an **outbox event** in one transaction; an async, idempotent relay updates the derived indexes; a periodic reconciliation job repairs drift.

> **Eventual consistency is acceptable here** — a chunk searchable two seconds late is fine. This path never touches money; transactional systems remain the record for wagers/balances.

### 14.2 Latency budget (p99 ≤ 800ms target)

| Stage | p99 | Mitigation |
|---|---|---|
| Routing | 5ms | CACHED/DIRECT short-circuit everything below |
| Dense ANN | 60ms | HNSW; tunable recall/latency knob |
| Graph BFS (3-hop) | 180ms | Hop cap + degree cap + precomputed hot neighbourhoods |
| Governance | 15ms | Predicate eval per candidate |
| Rerank | 350ms | Top-20 only; skippable under load |

### 14.3 Scale targets

Stateless retrievers behind a load balancer; vector index sharded per collection; async batched ingestion with backpressure.

- 50M+ chunks
- 10M+ graph nodes
- 500+ retrieval QPS

---

## 15. Threat Model

| Threat | Vector | Defense |
|---|---|---|
| **Indirect prompt injection** | Malicious instructions inside ingested content get executed | Instruction/data separation in prompt; provenance trust scoring; tool-call allow-listing; output validation |
| **Memory poisoning** | False user claims promoted to durable "fact" via compression | User claims never auto-promoted; provenance trust level; human-in-loop for high-sensitivity promotion |
| **Data exfiltration** | Crafted queries extract RESTRICTED content | ABAC fail-closed; per-principal retrieval-volume anomaly detection; rate limits |
| **Cross-domain leakage** | Agent retrieves content outside its jurisdiction/domain | Collection isolation; attribute match on jurisdiction; chunk-level sensitivity cap |
| **Embedding inversion** | Raw vectors partially reconstruct source text | Encrypt vectors at rest; access-control the raw store; never expose embeddings to clients |
| **Graph poisoning** | Adversarial input forces a wrong entity merge | Confidence threshold (<0.7 → new node, flagged); relationship provenance; integrity audit |

---

## 16. Error Handling & Edge Cases

| Case | Behaviour |
|---|---|
| Embedding model unavailable | Fall back to pure-Python vectoriser; log degraded mode; never crash the demo |
| No retrieval results | Agent answers from working memory / states it lacks grounded knowledge — never fabricates |
| Derived-index write fails post-commit | Outbox retries; reconciliation repairs; source of truth already durable |
| Entity resolution ambiguous (<0.7) | Create new node, flag for review; never silently merge two real entities |
| Access claim expired | Treat as no access (fail-closed); audit the denied attempt |
| Query exceeds context budget | Trim lowest-scored results first; keep working memory + top governed results |
