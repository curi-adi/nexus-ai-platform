"""Tests for retrieval components: BM25, RRF, Anti-RAG router, HybridRetriever."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nexus.retrieval.sparse import BM25Index
from nexus.retrieval.fusion import rrf
from nexus.retrieval.anti_rag import classify
from nexus.core.models import RetrievalStrategy, DataDomain, SensitivityLevel, AccessClaim
from nexus.embeddings.embedder import HashingEmbedder
from nexus.storage.vector_store import InMemoryVectorStore
from nexus.storage.metadata_store import MetadataStore
from nexus.storage.audit import AuditLog
from nexus.graph.knowledge_graph import KnowledgeGraph
from nexus.retrieval.retriever import HybridRetriever
import nexus.seed_data as seed_data


# ── BM25 ──────────────────────────────────────────────────────────────────────

def test_bm25_ranking():
    idx = BM25Index()
    idx.add("a", "the quick brown fox jumps")
    idx.add("b", "python is a great programming language for data science")
    idx.add("c", "the quick fox is very quick")
    results = idx.search("quick fox", top_k=3)
    ids = [r[0] for r in results]
    assert ids[0] in ("a", "c"), "quick fox should rank a or c first"

def test_bm25_absent_term():
    idx = BM25Index()
    idx.add("x", "hello world")
    assert idx.search("nexus") == []

def test_bm25_unique_term_ranks_first():
    idx = BM25Index()
    idx.add("a", "sports betting odds")
    idx.add("b", "compliance regulation jurisdiction nexus")
    idx.add("c", "product feature release")
    results = idx.search("nexus compliance")
    assert results[0][0] == "b"


# ── RRF ──────────────────────────────────────────────────────────────────────

def test_rrf_winner():
    fused = rrf([["x", "y"], ["x", "z"]])
    assert fused[0][0] == "x"

def test_rrf_all_lists():
    fused = rrf([["a", "b"], ["b", "a"]])
    ids = [f[0] for f in fused]
    assert "a" in ids and "b" in ids

def test_rrf_single_list():
    fused = rrf([["p", "q", "r"]])
    assert [f[0] for f in fused] == ["p", "q", "r"]


# ── Anti-RAG router ───────────────────────────────────────────────────────────

def test_classify_structured():
    strat = classify("what are the live odds right now", set())
    assert strat == RetrievalStrategy.STRUCTURED

def test_classify_direct():
    strat = classify("what is expected value", set())
    assert strat == RetrievalStrategy.DIRECT

def test_classify_graph():
    names = {"mahomes", "chiefs"}
    strat = classify("Mahomes and the Chiefs win", names)
    assert strat == RetrievalStrategy.GRAPH

def test_classify_hybrid_default():
    strat = classify("boosted odds policy", set())
    assert strat == RetrievalStrategy.HYBRID

def test_classify_cached():
    strat = classify("anything", set(), cache_hit=True)
    assert strat == RetrievalStrategy.CACHED


# ── End-to-end retriever ──────────────────────────────────────────────────────

@pytest.fixture
def full_retriever():
    embedder = HashingEmbedder()
    vstore   = InMemoryVectorStore()
    mstore   = MetadataStore()
    kg       = KnowledgeGraph()
    audit    = AuditLog()
    bm25     = BM25Index()

    seed_data.build(embedder, vstore, mstore, kg)
    for c in mstore.all_chunks():
        bm25.add(c.id, c.content)

    known_names: set[str] = set()
    for e in kg.all_entities():
        known_names.add(e.canonical_name.lower())
        for alias in e.aliases:
            known_names.add(alias.lower())

    retriever = HybridRetriever(bm25, embedder, vstore, mstore, kg, audit, known_names)
    return retriever, audit

def _global_claim():
    return AccessClaim(
        principal_id="test",
        domains=list(DataDomain),
        max_sensitivity=SensitivityLevel.RESTRICTED,
        attributes={"jurisdiction": "*"},
    )

def test_direct_returns_empty(full_retriever):
    retriever, _ = full_retriever
    strat, results = retriever.search(
        __import__("nexus.core.models", fromlist=["RetrievalRequest"]).RetrievalRequest(query="what is expected value"),
        _global_claim(),
    )
    assert strat == RetrievalStrategy.DIRECT
    assert results == []

def test_hybrid_returns_results(full_retriever):
    from nexus.core.models import RetrievalRequest
    retriever, _ = full_retriever
    strat, results = retriever.search(
        RetrievalRequest(query="NJ boosted odds rules"),
        _global_claim(),
    )
    assert strat in (RetrievalStrategy.HYBRID, RetrievalStrategy.GRAPH)
    assert len(results) > 0

def test_governance_excludes_restricted(full_retriever):
    from nexus.core.models import RetrievalRequest
    retriever, audit = full_retriever
    low_claim = AccessClaim(
        principal_id="low",
        domains=list(DataDomain),
        max_sensitivity=SensitivityLevel.INTERNAL,
        attributes={"jurisdiction": "*"},
    )
    _strat, results = retriever.search(
        RetrievalRequest(query="incident postmortem payout bug"),
        low_claim,
    )
    ids = [r.chunk.id for r in results]
    restricted_chunks = [
        c for c in __import__("nexus.storage.metadata_store", fromlist=["MetadataStore"])
        .__class__.__mro__  # just to check
    ]
    # The RESTRICTED chunk should not be in the results for a low-clearance claim
    for r in results:
        assert r.chunk.sensitivity != SensitivityLevel.RESTRICTED

def test_audit_records_excluded(full_retriever):
    from nexus.core.models import RetrievalRequest
    retriever, audit = full_retriever
    low_claim = AccessClaim(
        principal_id="lowaudit",
        domains=[DataDomain.COMPLIANCE],
        max_sensitivity=SensitivityLevel.INTERNAL,
        attributes={"jurisdiction": "NJ"},
    )
    retriever.search(RetrievalRequest(query="NJ odds rules"), low_claim)
    log = audit.dump()
    entry = next((e for e in log if e["principal_id"] == "lowaudit"), None)
    assert entry is not None
