# NEXUS — Guided Demo Walkthrough

A self-guided demo. Run each query, observe the result, and compare where indicated.

**Video walkthrough:** https://youtu.be/c_Y9eCdzPM8

---

## The Two Agents — What, Why, and How

The demo runs two agents side by side: **Agent A** and **Agent B**. They share the same knowledge store but see different results for the same query. This is the core governance demonstration.

### What they are

| | Agent A | Agent B |
|---|---|---|
| Label | Full Access | CA Analyst |
| Domains | All (Sports, Compliance, Product, Operations) | Sports, Product, Compliance only |
| Max sensitivity | RESTRICTED (sees everything) | INTERNAL (blocked from CONFIDENTIAL and RESTRICTED) |
| Jurisdiction | Global (all regions) | California only |

### Why two agents?

To prove that access control is **real and enforced at the retrieval layer** — not bolted on at the application layer. The same query, the same knowledge store, two different agents → two different result sets. Agent B never receives chunks it isn't allowed to see — they are removed inside the retriever before the answer is generated.

### How it works under the hood

Every knowledge chunk carries three access tags:
- **domain** — e.g. `COMPLIANCE`, `SPORTS`, `OPERATIONS`
- **sensitivity** — `PUBLIC` < `INTERNAL` < `CONFIDENTIAL` < `RESTRICTED`
- **jurisdiction** — e.g. `CA`, `NY` (or unset = global)

Every agent holds an `AccessClaim` declaring what it is permitted to see. The ABAC filter runs **after ranking but before results leave the retriever**:

```
retrieved chunks → RRF fusion → ABAC filter → results reach agent
                                     ↑
                              checks 3 conditions:
                              1. chunk.domain in claim.domains
                              2. chunk.sensitivity ≤ claim.max_sensitivity
                              3. chunk.jurisdiction matches claim.jurisdiction (or is unset)
```

Any chunk that fails a check is silently dropped. The count of excluded chunks and the reason are written to the **immutable audit log** — so there is always a record of what was blocked and why.

---

## Step 0 — Start the App

Open a terminal and run:

```
cd d:\deeplearning\Nexus\nexus_platform
python -m uvicorn app:app --port 8000
```

Then open your browser: **http://localhost:8000**

You should see a dark dashboard. The top bar shows: **6 chunks · 7 entities · hashing-256**

---

## The Screen Layout

```
┌─────────────────────────────────────────────────────────┐
│  Header: system stats · Agent A toggle · Agent B toggle │
├─────────────────────────────────────────────────────────┤
│  Query pills  [ LeBron? GRAPH ] [ Expected value? ] ... │
├──────────────────────────────┬──────────────────────────┤
│  Pipeline steps (animated)   │  Answer                  │
│  Retrieved chunks (cards)    │  Knowledge Graph         │
│                              │  Memory & Audit Log      │
└──────────────────────────────┴──────────────────────────┘
```

You will be switching between **Agent A** (Full Access) and **Agent B** (CA Analyst) in two of the demos to see how the same query returns different results depending on who is asking.

---

## Demo 1 — Knowledge Graph Routing

**Agent:** A (selected by default)

1. Click the pill: **`LeBron? GRAPH`**
2. Click the **Send** button (arrow icon)

**What to look for:**

- All 5 pipeline steps light up — the full retrieval ran
- Strategy badge: **GRAPH** (blue) — the system recognised "LeBron James" as a known entity and routed through the knowledge graph
- Knowledge cards appear with **SPORTS** domain badges
- Right panel → Knowledge Graph canvas: **LeBron and Lakers nodes glow**

> The system connected LeBron → Lakers → NBA automatically by traversing the graph — no keyword match needed.

---

## Demo 2 — Smart Routing (Zero Retrieval)

**Agent:** A

1. Click the pill: **`Expected value? DIRECT`**
2. Click **Send**

**What to look for:**

- Strategy badge: **DIRECT** (green)
- The middle pipeline steps (Dense · BM25 · Graph · RRF Fusion) are **grayed out**
- **No knowledge cards** — zero documents retrieved
- An answer is still returned immediately

**Compare to Demo 1:**

| | Demo 1 — LeBron | Demo 2 — Expected value |
|---|---|---|
| Strategy | GRAPH | DIRECT |
| Pipeline steps | All 5 active | Middle 4 grayed out |
| Documents retrieved | Yes | None |

> The system recognised this as a factual/math question it already knows — retrieving documents would only add noise and latency. It answered directly.

---

## Demo 3 — Access Control by Jurisdiction

**Same query. Two agents. Compare the results.**

### Run with Agent A (Full Access)

1. Make sure **Agent A** is selected (top left)
2. Click pill: **`CA data rules?`** → Send

Observe the chunk cards: you should see **both CA and NY** compliance cards returned.

---

### Run with Agent B (CA Analyst)

1. Click the **Agent B** toggle (top left)
2. Click the **same pill: `CA data rules?`** → Send

**What to compare:**

| | Agent A | Agent B |
|---|---|---|
| CA compliance chunk | Returned | Returned |
| NY compliance chunk | Returned | **Blocked** |
| ABAC Filter step | Green | **Red — 1 excluded** |
| Excl count (bottom right) | 0 | **1** |
| Audit Log entry | No exclusions | Exclusion recorded with reason |

> Agent B is scoped to California only. The New York compliance rule is blocked at the retrieval layer — it never enters the agent's context. The Audit Log records every blocked decision.

---

## Demo 4 — Access Control by Sensitivity Level

**Same query. Two agents. Compare the results.**

### Run with Agent A (Full Access)

1. Switch back to **Agent A**
2. Click pill: **`Postmortem`** → Send

Observe: a chunk card with a **red RESTRICTED badge** appears — this is an internal incident report.

---

### Run with Agent B (CA Analyst)

1. Switch to **Agent B**
2. Click the **same pill: `Postmortem`** → Send

**What to compare:**

| | Agent A | Agent B |
|---|---|---|
| Postmortem chunk | Visible (red RESTRICTED badge) | **Not returned** |
| ABAC Filter step | Green | **Red — 1 excluded** |
| Audit Log | No exclusions | Exclusion recorded |

> Agent B holds INTERNAL clearance only. The RESTRICTED postmortem is silently removed before results reach the agent. Same query, same knowledge store — a completely different (sanitised) result set.

---

## What the Four Demos Show

| Demo | Core capability demonstrated |
|---|---|
| 1 · LeBron / GRAPH | Intelligent routing: entity queries traverse the knowledge graph |
| 2 · Expected value / DIRECT | Intelligent routing: factual questions bypass retrieval entirely |
| 3 · CA data rules / jurisdiction | Access control: Agent B cannot see out-of-jurisdiction content |
| 4 · Postmortem / sensitivity | Access control: Agent B cannot see content above its clearance level |

The key design point across all four: **governance is enforced at the retrieval layer**, not the application layer — so restricted content never enters an agent's context window, regardless of how the agent is prompted.
