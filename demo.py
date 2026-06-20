"""
NEXUS — end-to-end demonstration script.

Run:
    python demo.py                  # stdlib-only fallbacks
    pip install -r requirements.txt && python demo.py  # full fidelity
"""
from __future__ import annotations
import sys, os

# Make nexus importable from this directory
sys.path.insert(0, os.path.dirname(__file__))

from nexus.core.config import SETTINGS
from nexus.core.models import DataDomain, SensitivityLevel, AccessClaim
from nexus.embeddings.embedder import get_embedder
from nexus.storage.vector_store import InMemoryVectorStore
from nexus.storage.metadata_store import MetadataStore
from nexus.storage.audit import AuditLog
from nexus.graph.knowledge_graph import KnowledgeGraph
from nexus.retrieval.sparse import BM25Index
from nexus.retrieval.retriever import HybridRetriever
from nexus.governance.provenance import ProvenanceStore
from nexus.memory.working import WorkingMemory
from nexus.memory.episodic import EpisodicMemory, extractive
from nexus.memory.semantic import SemanticMemory
from nexus.memory.manager import MemoryManager
from nexus.agents.base import ExtractiveAgent
import nexus.seed_data as seed_data


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def run_query(agent, label: str, query: str) -> None:
    print(f"\n  [{label}] Q: {query}")
    answer = agent.think(query)
    print(f"  [{label}] A: {answer[:300]}{'...' if len(answer) > 300 else ''}")


def main():
    # ── Composition root ──────────────────────────────────────────────────
    separator("NEXUS - Composition Root")
    print("  Initialising components...")

    embedder = get_embedder()
    print(f"  Embedder: {embedder.model_id}")

    vstore   = InMemoryVectorStore()
    mstore   = MetadataStore()
    kg       = KnowledgeGraph()
    audit    = AuditLog()
    bm25     = BM25Index()
    prov     = ProvenanceStore()

    # ── Seed the knowledge base ───────────────────────────────────────────
    separator("Seeding the Knowledge Base")
    seed_data.build(embedder, vstore, mstore, kg)
    chunks = mstore.all_chunks()
    print(f"  Chunks stored    : {len(chunks)}")
    print(f"  Entities in KG   : {len(kg.all_entities())}")
    for c in chunks:
        bm25.add(c.id, c.content)
    print(f"  BM25 index built : {bm25.N} docs")

    # Build the known_names set from the KG
    known_names: set[str] = set()
    for e in kg.all_entities():
        known_names.add(e.canonical_name.lower())
        for alias in e.aliases:
            known_names.add(alias.lower())

    # ── Wire retriever + memory ───────────────────────────────────────────
    retriever = HybridRetriever(bm25, embedder, vstore, mstore, kg, audit, known_names)
    semantic  = SemanticMemory(embedder, vstore, mstore)
    episodic  = EpisodicMemory(mstore, semantic, prov, summariser=extractive)
    memory    = MemoryManager(
        WorkingMemory(SETTINGS.working_capacity),
        episodic, semantic, retriever,
    )

    # ── Build agents ──────────────────────────────────────────────────────
    all_domains = list(DataDomain)

    A = ExtractiveAgent(
        "agentA", "s1", memory,
        AccessClaim(
            principal_id="A",
            domains=all_domains,
            max_sensitivity=SensitivityLevel.RESTRICTED,
            attributes={"jurisdiction": "*"},         # global principal
        ),
    )
    B = ExtractiveAgent(
        "agentB", "s2", memory,
        AccessClaim(
            principal_id="B",
            domains=[DataDomain.SPORTS, DataDomain.PRODUCT, DataDomain.COMPLIANCE],
            max_sensitivity=SensitivityLevel.INTERNAL,
            attributes={"jurisdiction": "NJ"},        # NJ analyst
        ),
    )

    # ── Demo queries ──────────────────────────────────────────────────────
    separator("Query 1 - Who is Patrick Mahomes? (GRAPH -> sports chunk; both agents)")
    run_query(A, "Agent-A", "Who is Patrick Mahomes?")
    run_query(B, "Agent-B", "Who is Patrick Mahomes?")

    separator("Query 2 - What is expected value? (DIRECT -> no retrieval)")
    run_query(A, "Agent-A", "What is expected value?")

    separator("Query 3 - NJ boosted odds rules? (A: sees NJ+PA; B: NJ only)")
    run_query(A, "Agent-A", "NJ boosted odds rules?")
    run_query(B, "Agent-B", "NJ boosted odds rules?")

    separator("Query 4 - Show the incident postmortem (A: RESTRICTED; B: excluded silently)")
    run_query(A, "Agent-A", "Show the incident postmortem")
    run_query(B, "Agent-B", "Show the incident postmortem")

    # ── Memory lifecycle: trigger compression ─────────────────────────────
    separator("Memory Lifecycle - 21 dummy turns through Agent A")
    for i in range(21):
        A.think(f"dummy question {i+1}")
    ep_traces = mstore.load_traces("agentA")
    compressed = [t for t in ep_traces if t.compressed_into is not None]
    print(f"  Total traces     : {len(ep_traces)}")
    print(f"  Compressed traces: {len(compressed)} (marked, not deleted)")

    # ── Audit log ─────────────────────────────────────────────────────────
    separator("Audit Log")
    log = audit.dump()
    print(f"  Total audit entries: {len(log)}")
    for entry in log[-5:]:
        excl = entry.get("excluded_count", 0)
        print(f"  [{entry['seq']:3d}] principal={entry['principal_id']} "
              f"strategy={entry['strategy']:10s} returned={len(entry['returned_ids'])} "
              f"excluded={excl}")

    separator("Done - NEXUS demo complete")


if __name__ == "__main__":
    main()
