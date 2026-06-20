# NEXUS — High-Level Design (HLD)

**Document:** High-Level Design (HLD)  
**Author:** Aditya Shrivastava  
**Version:** 0.1 · Draft  
**Companions:** [LLD](LLD.md) · [Implementation Guide](implementation.md)

---

## Contents

1. [Introduction — Purpose, Scope, Audience](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Architectural Principles](#3-architectural-principles)
4. [Architecture & Component View](#4-architecture--component-view)
5. [Component Responsibilities](#5-component-responsibilities)
6. [Key Data Flows](#6-key-data-flows)
7. [Technology Stack](#7-technology-stack)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Deployment View](#9-deployment-view)
10. [Assumptions, Constraints & Risks](#10-assumptions-constraints--risks)
11. [Phased Roadmap](#11-phased-roadmap)

---

## 1. Introduction

### 1.1 Purpose

This document defines the high-level architecture of **NEXUS**, a Context & Knowledge Platform that provides AI agents and applications with a single, governed source of enterprise context. It establishes the system boundaries, major components, and how they interact — at an altitude suitable for stakeholder review and as the basis for the detailed design (LLD).

### 1.2 Scope

| In scope | Out of scope |
|---|---|
| Knowledge ingestion & chunking · vector + graph storage · hybrid retrieval · agent memory tiers · retrieval governance (access control, provenance, audit) · a reusable agent interface | Model fine-tuning / training · being a raw data lake · sub-second streaming ingestion · replacing transactional systems of record (odds feeds, account balances) · the consuming agents' own business logic |

### 1.3 Intended Audience

Engineering leadership and reviewers, platform & AI engineers who will build on NEXUS, and security/compliance stakeholders assessing governance.

### 1.4 Glossary

| Term | Meaning |
|---|---|
| **Chunk** | The atomic unit of retrievable knowledge (a passage of text plus metadata). |
| **Collection** | A named namespace within the vector store (e.g. `compliance`, `sports`). |
| **RAG** | Retrieval-Augmented Generation — grounding an LLM's answer in retrieved knowledge. |
| **Knowledge Graph (KG)** | A typed graph of entities and relationships giving relational context. |
| **ABAC** | Attribute-Based Access Control — access decided by attributes, not just roles. |
| **Provenance** | The recorded lineage of how a piece of knowledge was created and used. |

---

## 2. System Overview

### 2.1 Problem

As an organization builds more AI features, each team independently builds its own retrieval pipeline, re-embeds the same documents into its own vector store, and invents its own chunking and memory handling. The result is duplicated effort, inconsistent answers, no shared notion of what the organization "knows," and — critically in a regulated environment — no consistent way to govern or audit what an AI surfaces.

### 2.2 Solution

NEXUS centralizes knowledge into one governed layer and exposes reusable primitives for retrieval, memory, and graph context. Teams build agents *on* NEXUS instead of rebuilding the substrate each time.

> **Core idea, in one line:** Knowledge goes in (chunked, tagged, linked); retrieval pulls the right pieces back; an agent answers grounded in them — with **memory** and **governance** as the two capabilities that make it a platform rather than a one-off RAG demo.

### 2.3 Objectives

| Objective | Description |
|---|---|
| **Reuse** | One set of retrieval / memory / governance primitives that any agent can consume. |
| **Quality** | Hybrid retrieval + graph context that beats naive single-method search. |
| **Trust** | Access control, provenance, and audit built into the critical path from day one. |

---

## 3. Architectural Principles

| # | Principle | What it means in practice |
|---|---|---|
| P1 | **Layered & modular** | Ingestion, storage, retrieval, memory, governance, and agent interface are separable layers with clear contracts. |
| P2 | **Pluggable backends** | Embedding model, vector store, and graph store sit behind interfaces — swappable without touching callers. |
| P3 | **Governance on the critical path** | Access control and provenance are inline in retrieval, not an optional add-on. |
| P4 | **Single system of record** | The metadata store is authoritative; vector index and graph are rebuildable projections of it. |
| P5 | **Start simple, layer complexity** | A minimal core runs first; graph, fusion, routing, and evaluation are additive layers. |

---

## 4. Architecture & Component View

NEXUS is a layered system. Agents consume context through a single interface; everything below is shared infrastructure.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  CONSUMERS            Copilots · Customer-service agents · Internal assistants  │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │  one interface
┌───────────────────────────────────▼───────────────────────────────────────────┐
│  AGENT INTERFACE      BaseAgent → MemoryManager.compile_context() → LLM         │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
┌───────────────────────────────────▼───────────────────────────────────────────┐
│  MEMORY               Working · Episodic · Semantic · Procedural tiers          │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
┌───────────────────────────────────▼───────────────────────────────────────────┐
│  RETRIEVAL            Anti-RAG router → (Sparse + Dense + Graph) → RRF fusion    │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
┌───────────────────────────────────▼───────────────────────────────────────────┐
│  STORAGE              Vector Store   ·   Knowledge Graph   ·   Metadata Store    │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
┌───────────────────────────────────▼───────────────────────────────────────────┐
│  INGESTION            Extract → Chunk → Tag → Embed → Link → Govern → Store      │
└───────────────────────────────────────────────────────────────────────────────┘

   GOVERNANCE  (cross-cutting):  Access Control (ABAC) · Provenance · Audit
```

### Layer Descriptions

| Layer | Sub-components | Key behaviour |
|---|---|---|
| **Consumers** | Copilots, agents, assistants | Never talk to storage directly — only through the agent interface. |
| **Agent Interface** | `BaseAgent` → `compile_context()` → LLM | A new agent is a small subclass; the whole memory lifecycle is inherited. |
| **Memory** | Working · Episodic · Semantic · Procedural | Four tiers from fast/small to slow/deep. Eviction demotes between tiers; compression is explicit and audited. |
| **Retrieval** | Anti-RAG router → BM25 + Dense + Graph → RRF | Routes the query, runs retrievers, fuses by RRF, then hands off to governance. |
| **Storage** | Vector Store · Knowledge Graph · Metadata DB | Metadata store is the system of record; vector index and KG are rebuildable projections. |
| **Ingestion** | Extract → Chunk → Embed → Link → Govern → Store | Idempotent on checksum; PII-scanned; provenance recorded for every chunk. |
| **Governance** *(cross-cutting)* | ABAC · Provenance · Audit | Woven through all layers. Fail-closed by default. |

### Query Flow — what the Anti-RAG router does per query type

| Query | Route chosen | Stages that run |
|---|---|---|
| "What rules apply to boosted odds in NJ?" | `HYBRID` | Input → Route → Retrieve → Fuse → Govern → Compile → Answer |
| "What are the live odds right now?" | `STRUCTURED` | Input → Route → *(skip 4 stages)* → Answer (delegated to API) |
| "What is expected value in betting?" | `DIRECT` | Input → Route → *(skip 4 stages)* → Answer (LLM answers directly) |
| "Which products does Mahomes appear in?" | `GRAPH` | Input → Route → Graph-RAG traversal → Fuse → Govern → Compile → Answer |

---

## 5. Component Responsibilities

| Component | Responsibility | Key collaborators |
|---|---|---|
| **Ingestion** | Turn source content into governed, embedded, graph-linked chunks. | Storage, Governance |
| **Vector Store** | Store chunk embeddings in namespaced collections; nearest-neighbour search. | Retrieval |
| **Knowledge Graph** | Hold entities & relationships; entity resolution; multi-hop traversal. | Retrieval, Ingestion |
| **Metadata Store** | System of record for chunks, provenance, access tags, audit log. | All |
| **Retrieval Engine** | Route the query, run sparse/dense/graph search, fuse and govern results. | Storage, Governance |
| **Memory Manager** | Manage the four memory tiers; compile the context window for an agent turn. | Retrieval, Storage |
| **Governance** | Enforce ABAC at retrieval, record provenance, write the audit trail. | Retrieval, Ingestion |
| **Agent Interface** | Reusable base class wiring memory + retrieval so a new agent is a small subclass. | Memory Manager |

---

## 6. Key Data Flows

### 6.1 Ingestion Flow

```
Source → Extract text/metadata → Chunk → Tag (domain, sensitivity, collection)
       → Embed → Link entities into Knowledge Graph → Record provenance → Store
```

### 6.2 Query / Answer Flow (one agent turn)

```
User input
  → store turn in Working + Episodic memory
  → Anti-RAG router: should we retrieve? which strategy?
  → Retrieval: Sparse + Dense + Graph  →  RRF fusion
  → Governance filter: drop chunks above the caller's access claim
  → compile context window (memory + results + active entities)
  → LLM answers, grounded
  → audit log records the decision
```

> **Why this ordering matters:** routing happens *before* retrieval (so we can skip it when retrieval would hurt), and governance happens *before* results reach the agent (so restricted content never enters the context window).

---

## 7. Technology Stack

Backends are pluggable (P2). The prototype favours zero-dependency, in-process choices; production swaps in scalable services without changing callers.

| Layer | Prototype | Production direction | Why pluggable |
|---|---|---|---|
| Embeddings | Local model / pure-Python fallback | Hosted embedding API or fine-tuned model | Quality vs. cost vs. data-residency tradeoffs differ by deployment |
| Vector store | In-memory index | Managed ANN service (HNSW-based) | Scale and persistence are deployment concerns, not design ones |
| Knowledge graph | In-memory graph | Managed graph database | Same graph API; storage changes underneath |
| Metadata / audit | SQLite | Managed relational DB + immutable object store | System of record must be durable in production |
| LLM | Extractive synthesizer (offline) | Hosted LLM (e.g. latest Claude models) | The agent interface isolates the model behind one seam |

---

## 8. Non-Functional Requirements

| Attribute | Target / Approach |
|---|---|
| **Performance** | Interactive retrieval latency budget (p99 sub-second); routing short-circuits unnecessary retrieval. |
| **Scalability** | Stateless retrieval behind a load balancer; storage sharded by collection; async ingestion. |
| **Security & Privacy** | ABAC at chunk level, fail-closed; PII detection at ingestion; encryption at rest. |
| **Auditability** | Every retrieval decision and ingestion is recorded in an append-only audit log. |
| **Consistency** | Metadata store authoritative; derived indexes eventually consistent and rebuildable. |
| **Reliability** | Idempotent ingestion; reconciliation reconverges any drift between stores. |
| **Extensibility** | New domains = new collections + ontology entries; new agents = a small subclass. |

---

## 9. Deployment View

| Mode | Description |
|---|---|
| **Prototype (single process)** | Everything runs in one Python process with in-memory stores and SQLite. Goal: demonstrate the full pipeline end-to-end with zero external services. |
| **Production (services)** | Retrieval and ingestion as horizontally-scaled services; managed vector store, graph DB, and relational DB; object store for audit; LLM accessed via API. Same interfaces, durable backends. |

---

## 10. Assumptions, Constraints & Risks

| Type | Item | Mitigation / Note |
|---|---|---|
| **Assumption** | Source content is accessible and reasonably structured for extraction. | Per-format extractors; messy sources degrade gracefully. |
| **Assumption** | Minutes-to-hours knowledge freshness is acceptable. | Real-time facts handled by structured systems, not NEXUS. |
| **Constraint** | Regulated domain — access control and audit are mandatory, not optional. | Governance designed into the critical path. |
| **Risk** | Retrieval quality degrades silently as content grows. | Evaluation harness as a gate (detailed in LLD). |
| **Risk** | Multi-store inconsistency on partial write failures. | Single system of record + reconciliation (detailed in LLD). |
| **Risk** | Retrieved content as a prompt-injection / poisoning vector. | Threat model + provenance trust (detailed in LLD). |

---

## 11. Phased Roadmap

Built in additive layers so each phase is independently demonstrable.

| Phase | Adds | Outcome |
|---|---|---|
| **V0** | Chunks + basic retrieval + an agent that answers | End-to-end loop works |
| **V1** | Dense embeddings + hybrid retrieval + RRF fusion | Retrieval quality |
| **V2** | Knowledge graph + entity resolution | Cross-domain reasoning |
| **V3** | ABAC governance + provenance + audit | Trust & compliance |
| **V4** | Four-tier memory + Anti-RAG router | Reusable agent memory |
| **V5** | Refactor into the platform package | Production-shaped primitives |

> The detailed design of every component above — data models, schemas, algorithms, interfaces, and sequence flows — is specified in the companion **[Low-Level Design (LLD)](LLD.md)**.
