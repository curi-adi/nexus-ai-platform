# NEXUS — Context & Knowledge Platform

A governed memory and knowledge layer for AI agents. NEXUS replaces bespoke per-team RAG pipelines with shared, production-grade primitives: hybrid retrieval with an anti-RAG router, a typed knowledge graph, three-tier agent memory, and attribute-based access control — all with an immutable audit trail.

Built for regulated environments where governance, provenance, and explainability are non-negotiable.

---

## Demo

[![NEXUS Demo](https://img.youtube.com/vi/c_Y9eCdzPM8/0.jpg)](https://youtu.be/c_Y9eCdzPM8)

See [WALKTHROUGH.md](WALKTHROUGH.md) for a step-by-step guided tour.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AI Agents (A, B, …)                        │
│                    ExtractiveAgent  ·  ClaudeAgent                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ .think(query)
┌────────────────────────────▼────────────────────────────────────────┐
│                        Memory Manager                                │
│   WorkingMemory (ring buffer)  →  EpisodicMemory (compressed)       │
│                             →  SemanticMemory (vector-indexed)       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                      Hybrid Retriever                                │
│                                                                      │
│   ┌─────────────────┐    classifies query intent                    │
│   │  Anti-RAG Router│ ──────────────────────────────────────────┐   │
│   └─────────────────┘                                           │   │
│                                                                  ▼   │
│   GRAPH ──► KG traversal + dense               DIRECT ──► skip all  │
│   HYBRID ──► dense + BM25 + graph ──► RRF    CACHED ──► return fast │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│   │ Dense Search │  │  BM25 Sparse │  │  Graph RAG   │             │
│   │ (embeddings) │  │ (term-freq)  │  │ (BFS on KG)  │             │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│          └─────────────────▼──────────────────┘                     │
│                      RRF Fusion                                      │
│                      ABAC Filter  ◄── access claim (agent)          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                        Storage Layer                                 │
│   InMemoryVectorStore  ·  MetadataStore  ·  KnowledgeGraph          │
│   AuditLog  ·  ProvenanceStore                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features

### Anti-RAG Router
Every query is classified before retrieval fires. The router picks the optimal strategy:

| Strategy | Trigger | Behaviour |
|---|---|---|
| `GRAPH` | Named entity detected | KG traversal → entity-linked chunks |
| `HYBRID` | Broad / mixed query | Dense + BM25 + Graph → RRF merge |
| `DIRECT` | Factual / math question | Skip knowledge store entirely |
| `STRUCTURED` | Structured data query | Route to structured lookup |
| `CACHED` | Seen recently | Return cached result |

DIRECT routing eliminates retrieval latency and avoids injecting irrelevant context for questions that don't need it.

### Knowledge Graph & Ontology
- Typed entities: `PLAYER`, `TEAM`, `LEAGUE`, `REGULATION`, `JURISDICTION`, `PRODUCT`, `EVENT`
- Typed relationships with weights
- BFS traversal with configurable hop depth and degree cap
- Entity resolution with confidence ladder and alias management
- Graph RAG: seed from matched entities → expand neighbours → retrieve linked chunks

### Three-Tier Agent Memory

```
Working Memory   ──►  short-term ring buffer (configurable capacity)
      │
      ▼ (eviction)
Episodic Memory  ──►  full trace log + extractive compression of old episodes
      │
      ▼ (vector-indexed)
Semantic Memory  ──►  long-term recall via embedding similarity
```

All three tiers are coordinated by `MemoryManager` and shared across agent sessions.

### ABAC Governance
Every chunk carries `domain`, `sensitivity`, and `jurisdiction` metadata. Every agent holds an `AccessClaim` specifying its allowed domains, maximum sensitivity level, and jurisdiction scope. The ABAC layer enforces these at retrieval time — not at the application layer.

```python
# Agent A — full access
AccessClaim(principal_id="A", domains=all_domains,
            max_sensitivity=SensitivityLevel.RESTRICTED,
            attributes={"jurisdiction": "*"})

# Agent B — CA Analyst (restricted)
AccessClaim(principal_id="B",
            domains=[DataDomain.SPORTS, DataDomain.PRODUCT, DataDomain.COMPLIANCE],
            max_sensitivity=SensitivityLevel.INTERNAL,
            attributes={"jurisdiction": "CA"})
```

Same query, different agents → different chunks returned. Every exclusion is recorded in the audit log.

### Immutable Audit Trail
Every query produces an audit entry:
- Principal ID, query, strategy chosen
- Chunk IDs returned
- Count of chunks excluded by ABAC
- Sequence number (monotonic)

---

## Project Structure

```
nexus_platform/
├── app.py                      # FastAPI server
├── demo.py                     # Terminal demo (no install needed)
├── static/
│   ├── index.html              # Web UI — pipeline visualisation + KG canvas
│   └── guide.html              # Interactive demo guide
├── nexus/
│   ├── core/                   # Models, config, errors, utils
│   ├── embeddings/             # HashingEmbedder (stdlib) + LocalEmbedder
│   ├── storage/                # VectorStore, MetadataStore, AuditLog
│   ├── ingestion/              # Chunker, PII scanner, pipeline
│   ├── retrieval/              # Anti-RAG router, BM25, dense, RRF, HybridRetriever
│   ├── graph/                  # KnowledgeGraph, entity resolution, ontology
│   ├── memory/                 # Working, Episodic, Semantic, MemoryManager
│   ├── governance/             # ABAC permits(), ProvenanceStore
│   ├── agents/                 # BaseAgent, ExtractiveAgent, ClaudeAgent
│   └── eval/                   # recall@k, MRR, nDCG, GoldenSet
└── tests/                      # 46 tests, all passing
```

---

## Quick Start

**Zero external dependencies** — runs on stdlib + Python 3.8+.

```bash
# Clone
git clone https://github.com/curi-adi/nexus-ai-platform.git
cd nexus-ai-platform

# Terminal demo
python demo.py

# Web UI
pip install fastapi uvicorn
python -m uvicorn app:app --port 8000
# Open http://localhost:8000
```

Optional upgrades:
```bash
pip install sentence-transformers   # real embeddings (replaces HashingEmbedder)
pip install anthropic               # Claude-powered agent answers
```

---

## Running Tests

```bash
pip install pytest pydantic
pytest tests/ -v
```

All 46 tests pass against the in-memory implementation with no external services required.

---

## Web UI

The single-page UI at `http://localhost:8000` shows the full system in action:

- **Pipeline visualisation** — animated step-by-step view of every query moving through Anti-RAG → Strategy → Retrieval → RRF → ABAC → Results
- **Chunk cards** — domain, sensitivity, RRF score, and which retrievers (dense / sparse / graph) found each result
- **Knowledge Graph canvas** — entity nodes glow when referenced in retrieved chunks
- **Memory & Audit panel** — working memory fill level, episodic compression count, excluded chunk count, live audit log

![Pipeline: Query → Anti-RAG Router → Strategy → Dense+BM25+Graph → RRF Fusion → ABAC Filter → Results]

---

## Design Decisions

**Why anti-RAG?** Standard RAG always retrieves — even for math questions or factual lookups where the model already knows the answer. The Anti-RAG Router classifies query intent first and skips the knowledge store when retrieval adds noise, not signal.

**Why RRF over score normalisation?** Dense similarity scores and BM25 scores live on incompatible scales. Reciprocal Rank Fusion merges ranked lists by position, not score magnitude — no tuning of scale factors needed.

**Why three-tier memory?** Working memory is fast but bounded. Episodic memory preserves full conversation traces but compresses old ones to save space. Semantic memory enables long-range recall via similarity. Each tier serves a different retrieval horizon.

**Why ABAC at the retrieval layer?** Application-layer filtering can be bypassed or forgotten. Enforcing access control inside the retriever — before chunks ever reach the agent — means governance cannot be accidentally skipped by any caller.

---

## Code Walkthrough

### End-to-End Flow — what happens when you submit a query

```
agent.think("Who is LeBron James?")
  │
  ├─ 1. MemoryManager.retrieve_context(query)
  │       └─ WorkingMemory.search()      → recent turns matching the query
  │       └─ EpisodicMemory.recall()     → compressed past episodes
  │       └─ SemanticMemory.search()     → long-range vector recall
  │
  ├─ 2. HybridRetriever.search(req, claim)
  │       └─ anti_rag.classify(query, known_names)
  │               → detects "LeBron" in known_names → GRAPH strategy
  │
  │       └─ dense_search()    → embed query → cosine similarity over VectorStore
  │       └─ bm25.search()     → term-frequency match over all chunk tokens
  │       └─ graph_search()    → resolve entity → BFS on KG → chunk IDs of neighbours
  │
  │       └─ rrf([dense_ids, sparse_ids, graph_ids])
  │               → merge three ranked lists by reciprocal rank position
  │
  │       └─ ABAC filter: permits(claim, chunk) for each fused chunk
  │               → drop chunks where sensitivity > claim.max_sensitivity
  │               → drop chunks where jurisdiction not in claim.attributes
  │
  ├─ 3. Agent builds prompt from context + retrieved chunks
  │
  ├─ 4. Agent generates answer (extractive or via Claude API)
  │
  └─ 5. MemoryManager.store(query, answer)
          └─ WorkingMemory.add()         → push to ring buffer
          └─ EpisodicMemory.record()     → append trace, compress if buffer full
```

---

### Module Reference

#### `nexus/core/models.py` — Data contracts
Every object in the system is a Pydantic model defined here. Key types:

```python
KnowledgeChunk      # a retrievable document fragment
  .id               # UUID
  .content          # raw text
  .domain           # DataDomain enum (SPORTS, COMPLIANCE, OPERATIONS…)
  .sensitivity      # SensitivityLevel enum (PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED)
  .entity_refs      # List[str] — entity IDs mentioned in this chunk
  .jurisdiction     # optional geographic scope

Entity              # a node in the knowledge graph
  .canonical_name   # primary name
  .aliases          # List[str] — alternate names for resolution
  .entity_type      # EntityType enum (PLAYER, TEAM, LEAGUE, REGULATION…)

Relationship        # a typed edge in the knowledge graph
  .source_entity_id
  .target_entity_id
  .relation_type    # e.g. "PLAYS_FOR", "GOVERNED_BY", "OPERATES_IN"
  .weight           # float — used to prioritise BFS traversal

AccessClaim         # what an agent is allowed to see
  .principal_id
  .domains          # List[DataDomain]
  .max_sensitivity  # ceiling sensitivity level
  .attributes       # {"jurisdiction": "NJ"} etc.

RetrievalResult     # one ranked result
  .chunk            # KnowledgeChunk
  .score            # RRF score
  .strategy         # which RetrievalStrategy produced this
  .explanation      # "dense,graph" — which retrievers found it
```

---

#### `nexus/retrieval/anti_rag.py` — The router
```python
def classify(query: str, known_names: Set[str]) -> RetrievalStrategy:
```
Scans the query tokens against `known_names` (all entity canonical names + aliases).
- Any match → `GRAPH`
- Math / definition keywords → `DIRECT`
- Otherwise → `HYBRID`

This runs before any embedding or index lookup — it's pure string matching, O(tokens).

---

#### `nexus/retrieval/retriever.py` — HybridRetriever
Orchestrates the full retrieval pipeline.

```python
def search(self, req: RetrievalRequest, claim: AccessClaim):
    strat = classify(req.query, self.known_names)

    if strat in (DIRECT, STRUCTURED, CACHED):
        return strat, []          # skip everything

    dense  = dense_search(...)    # top-k by cosine similarity
    sparse = self.bm25.search(...)# top-k by BM25 score
    graph  = graph_search(...)    # top-k via KG BFS

    fused  = rrf([dense_ids, sparse_ids, graph_ids])  # merge by rank

    results = [r for r in fused if permits(claim, chunk)]  # ABAC

    # expose for API without double-retrieval
    self.last_strategy = strat
    self.last_results  = results
    self.last_excluded = excluded_count
```

The `last_*` fields let the FastAPI layer read retrieval metadata without calling search() a second time.

---

#### `nexus/retrieval/fusion.py` — RRF
```python
def rrf(ranked_lists: List[List[str]], k: int = 60) -> List[Tuple[str, float]]:
```
For each document ID, accumulates `1 / (k + rank)` across all lists. Returns a merged ranking sorted by total score. `k=60` is the standard constant that down-weights top-ranked outliers.

Why RRF over score normalisation: dense similarity scores and BM25 scores are on incompatible scales. RRF uses rank position only — no calibration needed.

---

#### `nexus/graph/knowledge_graph.py` — KnowledgeGraph
```python
class KnowledgeGraph:
    entities: Dict[str, Entity]              # id → Entity
    by_canon: Dict[str, str]                 # canonical_name → id
    by_alias: Dict[str, str]                 # alias → id
    adj:      Dict[str, List[Tuple[str, float]]]  # id → [(neighbour_id, weight)]
    _rels:    List[Relationship]             # full relationship objects for the API
```

`neighbors(seed_ids, max_hops, degree_cap)` runs BFS, prioritising the highest-weight edges at each node, up to `degree_cap` neighbours per hop and `max_hops` depth.

`_rels` stores full `Relationship` objects separately from `adj` — the adjacency list only stores `(id, weight)` for fast BFS, losing the `relation_type` string. `_rels` preserves the typed edge for the KG canvas API.

---

#### `nexus/retrieval/graph_rag.py` — Graph RAG
```python
def graph_search(query, kg, embedder, known_names, top_k):
    # 1. resolve entity seeds from query tokens
    seeds = [kg.by_canon[t] for t in tokens if t in kg.by_canon]
    seeds += [kg.by_alias[t] for t in tokens if t in kg.by_alias]

    # 2. BFS expand from seeds
    neighbourhood = kg.neighbors(seeds, max_hops=2, degree_cap=5)

    # 3. collect chunks whose entity_refs intersect the neighbourhood
    # 4. rank by hop distance (closer = higher score)
```

---

#### `nexus/governance/access.py` — ABAC
```python
def permits(claim: AccessClaim, chunk: KnowledgeChunk) -> bool:
    if chunk.domain not in claim.domains:            return False
    if chunk.sensitivity > claim.max_sensitivity:    return False
    if chunk.jurisdiction:
        jur = claim.attributes.get("jurisdiction","*")
        if jur != "*" and jur != chunk.jurisdiction: return False
    return True
```
Three independent checks: domain allowlist, sensitivity ceiling, jurisdiction match. All must pass.

---

#### `nexus/memory/` — Three-tier memory

**`working.py` — WorkingMemory**
Ring buffer of the last N interactions (default N=10). `search()` does substring match over content. When the buffer is full, the oldest entry is evicted to episodic memory.

**`episodic.py` — EpisodicMemory**
Stores full `MemoryTrace` objects (query, answer, timestamp, chunks used). When the trace count exceeds a threshold, old traces are compressed via an extractive summariser (picks the highest-scoring sentence) and the originals are marked `compressed_into`. Compressed traces are retained as metadata; their content is replaced by the summary.

**`semantic.py` — SemanticMemory**
Embeds and stores chunks into the shared `VectorStore`. `search()` embeds the query and runs cosine similarity — enabling cross-session recall of anything previously ingested.

**`manager.py` — MemoryManager**
Coordinates all three tiers:
- On retrieve: queries all three and merges results
- On store: writes to working memory and episodic; semantic is populated during ingestion

---

#### `nexus/ingestion/pipeline.py` — Ingestion
```
raw text → Chunker (fixed-size with overlap)
         → PII scanner (regex-based redaction)
         → embed (HashingEmbedder or LocalEmbedder)
         → VectorStore.add()
         → MetadataStore.save_chunk()
```
The PII scanner redacts patterns for emails, phone numbers, SSNs, and credit card numbers before any chunk is stored.

---

#### `nexus/embeddings/embedder.py` — Pluggable embedders

```python
class HashingEmbedder:   # stdlib only — deterministic, no model download
class LocalEmbedder:     # wraps sentence-transformers, same interface
```
Both expose `.embed(text) -> List[float]` and `.model_id`. The retriever and memory layers call the interface — swapping the embedder requires no other code change.

---

#### `nexus/eval/` — Evaluation
```python
recall_at_k(retrieved_ids, relevant_ids, k)   # fraction of relevant docs in top-k
mrr(retrieved_ids, relevant_ids)              # mean reciprocal rank
ndcg(retrieved_ids, relevant_ids, k)          # normalised discounted cumulative gain
```
`GoldenSet` stores (query, expected_chunk_ids) pairs and runs all three metrics against the retriever in one call.

---

#### `app.py` — FastAPI server

| Endpoint | Purpose |
|---|---|
| `POST /api/query` | Run a query through an agent; returns strategy, chunks, answer, memory stats |
| `GET /api/graph` | Return all entities and relationships for the KG canvas |
| `GET /api/audit` | Return the full audit log |
| `GET /api/info` | Return chunk count, entity count, embedder model |
| `GET /` | Serve the web UI |

The server initialises all NEXUS components once at startup (same as `demo.py`) and keeps them in module-level state — intentional for a single-process demo server.

---

## Tech Stack

- **Python 3.8+** — `from __future__ import annotations` + typing module throughout
- **FastAPI + uvicorn** — async web server
- **Pydantic v2** — data models and validation
- **Pure stdlib** — no vector DB, no graph DB, no ML framework required to run
- **Optional**: `sentence-transformers` for dense embeddings, `anthropic` for LLM answers
