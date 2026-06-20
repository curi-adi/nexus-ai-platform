# NEXUS — Demo Guide for Video Recording

---

## What Is NEXUS? (Your 30-second pitch)

> "NEXUS is a governed memory and knowledge layer that sits between your AI agents and your data. Instead of every team building their own RAG pipeline, NEXUS gives you one central place — with intelligent routing, a knowledge graph, tiered memory, and access control baked in. I built the full platform in Python — from the vector store to the query pipeline to the governance layer."

---

## Before You Start: Launch the Server

Open a terminal, run these two commands:

```
cd d:\deeplearning\Nexus\nexus_platform
python -m uvicorn app:app --port 8000
```

Then open your browser to: **http://localhost:8000**

You'll see the NEXUS UI load. The header bar will show:
- **6 chunks** — documents in the knowledge store
- **7 entities** — nodes in the knowledge graph  
- **hashing-256** — the embedding model in use

---

## The UI at a Glance

The screen is split into three zones:

```
┌────────────────────────────────────────────────────────────┐
│  HEADER: system stats (chunks / entities / embedder)       │
├────────────────────────────────────────────────────────────┤
│  QUERY BAR: Agent toggle | Preset pills | Text input       │
├─────────────────────────────────────┬──────────────────────┤
│  QUERY PIPELINE (animated steps)    │  ANSWER              │
│                                     │  KNOWLEDGE GRAPH     │
│  RETRIEVED CHUNKS (cards)           │  MEMORY & AUDIT      │
└─────────────────────────────────────┴──────────────────────┘
```

---

## Key Concepts to Know Before Recording

### 1. Two Agents with Different Permissions

| | Agent A | Agent B |
|---|---|---|
| Label | Full Access | NJ Analyst |
| Max sensitivity | RESTRICTED (highest) | INTERNAL only |
| Jurisdiction | Global | New Jersey only |
| Access to | All domains | Sports, Product, Compliance |

**What this means:** Same query, different agents → different chunks returned. Agent B is blocked from RESTRICTED content and from non-NJ compliance rules.

### 2. The Anti-RAG Router (the smart part)

Every query first goes through the Anti-RAG Router. It classifies the query and picks a strategy:

| Strategy | Color | What Happens |
|---|---|---|
| **GRAPH** | Blue | Query mentions a known entity → knowledge graph traversal first |
| **HYBRID** | Violet | Mixed query → run all three retrievers (dense + BM25 + graph) |
| **DIRECT** | Green | Factual/math question → skip retrieval entirely, answer directly |
| **STRUCTURED** | Orange | Structured data query → skip to structured lookup |
| **CACHED** | Yellow | Already answered recently → return from cache |

**The key insight:** "Traditional RAG always retrieves — even for a math question. NEXUS's Anti-RAG Router skips the knowledge store when retrieval adds no value. This saves latency and avoids injecting irrelevant context."

### 3. The Query Pipeline (the animated steps)

Watch the steps light up left to right after you submit a query:

1. **Query** — your question enters the system
2. **Anti-RAG Router** — classifies the query intent
3. **Strategy badge** — the chosen strategy lights up with a color
4. **Dense + BM25 + Graph** — three retrievers run in parallel (grayed out if DIRECT)
5. **RRF Fusion** — Reciprocal Rank Fusion merges the three ranked lists into one
6. **ABAC Filter** — access control checks each chunk against the agent's permissions
7. **Results** — final chunks passed back

### 4. Retrieved Chunks (the cards)

Each card shows:
- **Domain badge** (SPORTS, COMPLIANCE, OPERATIONS, etc.) — color-coded
- **Sensitivity badge** — PUBLIC (green) / INTERNAL (blue) / CONFIDENTIAL (yellow) / RESTRICTED (red)
- **RRF score** — how relevant the chunk is (higher = better match)
- **Source tags** — `dense`, `sparse`, `graph` — which retrievers found this chunk
- **Content preview** — first 260 characters of the chunk

### 5. Knowledge Graph (right panel, canvas)

7 entities arranged in a circle. After a query, entities referenced in the retrieved chunks **glow and expand** — showing which parts of the knowledge graph were activated.

Entity type colors:
- Blue = PLAYER
- Green = TEAM  
- Yellow = LEAGUE
- Orange = REGULATION
- Violet = PRODUCT
- Pink = JURISDICTION
- Red = EVENT

### 6. Memory & Audit (bottom right)

- **Working Memory bar** — shows how many of the 10 working memory slots are used (fills up as queries accumulate)
- **Episodic count** — total memory traces stored (conversations remembered)
- **Compressed** — old memories that were summarized to save space
- **Excl (excluded)** — chunks blocked by ABAC in the last query
- **Audit Log** — every query logged with principal, strategy, results returned, chunks excluded

---

## Demo Script: 4 Queries to Record

### Demo 1: Knowledge Graph Routing
**Click preset:** "Mahomes? GRAPH"  
**Agent:** A (Full Access)

What to say:
> "I'm asking about Patrick Mahomes — a named entity in the system. Watch the pipeline. The Anti-RAG Router recognizes 'Mahomes' as a known entity, routes to GRAPH strategy. The knowledge graph traversal fires, finds Mahomes, then expands to connected entities — his team, his league. Six chunks come back. Notice the Knowledge Graph on the right — those blue and green nodes are glowing because they were referenced in the results."

**What you'll see:** Strategy badge turns blue (GRAPH). All pipeline steps light up. 6 chunk cards appear with SPORTS domain. On the KG canvas, Mahomes + Chiefs nodes glow.

---

### Demo 2: Anti-RAG Bypass (the wow moment)
**Click preset:** "Expected value? DIRECT"  
**Agent:** A

What to say:
> "Now watch what happens with a factual math question. The Anti-RAG Router classifies this as DIRECT — it already knows the answer without searching any documents. The retrieval steps dim out entirely. We skip Dense, BM25, Graph, and RRF. Zero chunks are retrieved, the answer is returned immediately. This is the core value of the Anti-RAG Router — no hallucination risk from irrelevant retrieved context, and much lower latency."

**What you'll see:** Strategy turns green (DIRECT). The "Dense + BM25 + Graph", "RRF Fusion", and "ABAC Filter" steps gray out completely. Chunk area shows "No retrieval — DIRECT routing skipped the knowledge store".

---

### Demo 3: ABAC Governance (the governance proof)
**Click preset:** "NJ odds rules?" or "NJ boosted odds rules?"  
**Agent:** A first, then switch to B

**With Agent A:**
> "Agent A has global jurisdiction and RESTRICTED access. It gets back compliance chunks from all jurisdictions — PA, NJ, general rules."

**Switch to Agent B, run same query:**
> "Agent B is configured as an NJ Analyst — Internal clearance only, New Jersey jurisdiction. Watch the ABAC Filter step. It now shows 1 excluded in red. The Pennsylvania compliance chunk is blocked. The Audit Log records exactly what was excluded and why. This is ABAC — Attribute-Based Access Control — enforced at the retrieval layer, not the application layer."

**What you'll see:** Agent B query → ABAC step turns red, shows "1 excluded". Excluded count in Memory & Audit shows 1. Audit log entry shows `excl: 1`.

---

### Demo 4: ABAC on RESTRICTED Content
**Click preset:** "Postmortem ABAC"  
**Agent:** A first, then B

**With Agent A:**
> "The postmortem is tagged RESTRICTED — the highest sensitivity level. Agent A has RESTRICTED clearance, so it gets the chunk."

**Switch to Agent B:**
> "Agent B only has INTERNAL clearance. The RESTRICTED postmortem chunk is blocked. Same query, same knowledge store — but Agent B sees a completely different (sanitized) result set. Every access decision is logged in the immutable audit trail."

**What you'll see:** Agent B → postmortem chunk is missing from results, excluded count goes up, audit entry shows exclusion.

---

## What to Highlight as Engineering Decisions

If the interviewer asks "how does this work under the hood":

**1. No double-retrieval problem:**
> "The retriever stores the last strategy, results, and excluded count as instance variables. The API reads them after agent.think() returns — no second retrieval, no double audit entries."

**2. RRF Fusion:**
> "Dense retrieval uses cosine similarity on embeddings. BM25 is term-frequency sparse search. Graph RAG expands from entity seeds via BFS. The three ranked lists are merged using Reciprocal Rank Fusion — a rank-based merging algorithm that's robust to score scale differences between retrievers."

**3. KG relationships stored twice:**
> "The KnowledgeGraph.adj dict stores (target_id, weight) for BFS traversal. But that loses the relation_type string. So I added a separate _rels list that stores full Relationship objects — the UI reads those to draw labeled edges on the canvas."

**4. Python 3.8 compatibility:**
> "The platform runs on Python 3.8 using from __future__ import annotations and the typing module throughout — no 3.10+ union syntax or 3.9+ generic collections."

---

## Quick Reference: File Structure

```
nexus_platform/
├── app.py                   ← FastAPI server (what uvicorn runs)
├── static/index.html        ← This entire UI (single file)
├── demo.py                  ← Terminal demo (no UI)
├── nexus/
│   ├── core/                ← Models (chunks, entities, access claims)
│   ├── embeddings/          ← HashingEmbedder (no install needed)
│   ├── storage/             ← Vector store, metadata, audit log
│   ├── retrieval/           ← Anti-RAG router, BM25, dense, RRF, hybrid
│   ├── graph/               ← KnowledgeGraph (BFS traversal)
│   ├── memory/              ← Working, Episodic, Semantic, MemoryManager
│   ├── governance/          ← ABAC permits(), ProvenanceStore
│   └── agents/              ← ExtractiveAgent (the thing you query)
└── tests/                   ← 46 tests, all passing
```

---

## If Something Breaks During Recording

**Server not running:**
```
cd d:\deeplearning\Nexus\nexus_platform
python -m uvicorn app:app --port 8000
```

**Port already in use:**
```
python -m uvicorn app:app --port 8001
```
Then go to http://localhost:8001

**Browser shows old version:** Hard refresh with Ctrl+Shift+R

**Chunks don't appear:** The server may have restarted and lost in-memory state — just restart uvicorn.
