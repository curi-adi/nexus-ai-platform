# NEXUS — Context & Knowledge Platform

A governed memory and knowledge layer for AI agents. NEXUS replaces bespoke per-team RAG pipelines with shared, production-grade primitives: hybrid retrieval with an anti-RAG router, a typed knowledge graph, three-tier agent memory, and attribute-based access control — all with an immutable audit trail.

Built for regulated environments where governance, provenance, and explainability are non-negotiable.

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

# Agent B — restricted analyst
AccessClaim(principal_id="B",
            domains=[DataDomain.SPORTS, DataDomain.COMPLIANCE],
            max_sensitivity=SensitivityLevel.INTERNAL,
            attributes={"jurisdiction": "NJ"})
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

## Tech Stack

- **Python 3.8+** — `from __future__ import annotations` + typing module throughout
- **FastAPI + uvicorn** — async web server
- **Pydantic v2** — data models and validation
- **Pure stdlib** — no vector DB, no graph DB, no ML framework required to run
- **Optional**: `sentence-transformers` for dense embeddings, `anthropic` for LLM answers
