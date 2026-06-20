"""Tests for memory tiers: working eviction, episodic compression, manager wiring."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nexus.memory.working import WorkingMemory
from nexus.memory.episodic import EpisodicMemory, extractive
from nexus.memory.semantic import SemanticMemory
from nexus.memory.manager import MemoryManager
from nexus.storage.metadata_store import MetadataStore
from nexus.storage.vector_store import InMemoryVectorStore
from nexus.governance.provenance import ProvenanceStore
from nexus.embeddings.embedder import HashingEmbedder
from nexus.core.models import MemoryTrace, DataDomain, SensitivityLevel, AccessClaim
from nexus.core.config import SETTINGS


def make_trace(agent_id="a", session_id="s", turn=1, role="user", content="hello"):
    return MemoryTrace(
        agent_id=agent_id,
        session_id=session_id,
        turn_index=turn,
        role=role,
        content=content,
    )


# ── WorkingMemory ─────────────────────────────────────────────────────────────

def test_working_no_eviction_under_capacity():
    wm = WorkingMemory(capacity=2)
    t1, t2 = make_trace(turn=1), make_trace(turn=2)
    assert wm.push(t1) is None
    assert wm.push(t2) is None

def test_working_eviction_on_overflow():
    wm = WorkingMemory(capacity=2)
    t1, t2, t3 = make_trace(turn=1), make_trace(turn=2), make_trace(turn=3)
    wm.push(t1); wm.push(t2)
    evicted = wm.push(t3)
    assert evicted is not None
    assert evicted.turn_index == 1
    assert len(wm.all()) == 2

def test_working_all_correct_order():
    wm = WorkingMemory(capacity=2)
    t1, t2, t3 = make_trace(turn=1), make_trace(turn=2), make_trace(turn=3)
    wm.push(t1); wm.push(t2); wm.push(t3)
    all_turns = [t.turn_index for t in wm.all()]
    assert all_turns == [2, 3]


# ── EpisodicMemory compression ────────────────────────────────────────────────

def test_episodic_compression_marks_not_deletes():
    mstore  = MetadataStore()
    embedder = HashingEmbedder()
    vstore  = InMemoryVectorStore()
    prov    = ProvenanceStore()
    semantic = SemanticMemory(embedder, vstore, mstore)
    episodic = EpisodicMemory(mstore, semantic, prov, summariser=extractive)

    agent_id = "compressA"
    compress_at = SETTINGS.episodic_compress_at

    for i in range(compress_at):
        t = make_trace(agent_id=agent_id, turn=i, content=f"turn {i}")
        episodic.store(t)

    assert episodic.should_compress(agent_id)
    chunk = episodic.compress(agent_id)

    all_traces = mstore.load_traces(agent_id)
    compressed = [t for t in all_traces if t.compressed_into is not None]
    assert len(all_traces) == compress_at         # none deleted
    assert len(compressed) == compress_at         # all marked
    assert all(t.compressed_into == chunk.id for t in compressed)

def test_episodic_no_compress_under_threshold():
    mstore  = MetadataStore()
    embedder = HashingEmbedder()
    vstore  = InMemoryVectorStore()
    prov    = ProvenanceStore()
    semantic = SemanticMemory(embedder, vstore, mstore)
    episodic = EpisodicMemory(mstore, semantic, prov)

    for i in range(5):
        episodic.store(make_trace(agent_id="b", turn=i))
    assert not episodic.should_compress("b")


# ── MemoryManager wiring ──────────────────────────────────────────────────────

class _DummyRetriever:
    def search(self, req, claim):
        from nexus.core.models import RetrievalStrategy
        return RetrievalStrategy.DIRECT, []

def _build_manager(capacity=10):
    mstore   = MetadataStore()
    embedder = HashingEmbedder()
    vstore   = InMemoryVectorStore()
    prov     = ProvenanceStore()
    semantic = SemanticMemory(embedder, vstore, mstore)
    episodic = EpisodicMemory(mstore, semantic, prov, summariser=extractive)
    working  = WorkingMemory(capacity=capacity)
    retriever = _DummyRetriever()
    return MemoryManager(working, episodic, semantic, retriever), mstore

def test_manager_working_does_not_exceed_capacity():
    manager, _ = _build_manager(capacity=3)
    claim = AccessClaim(principal_id="x", domains=list(DataDomain))
    for i in range(5):
        manager.acquire(make_trace(agent_id="x", turn=i))
    ctx = manager.compile_context("x", "s", [])
    assert len(ctx.working_memory) <= 3

def test_manager_episodic_receives_overflow():
    manager, mstore = _build_manager(capacity=2)
    for i in range(4):
        manager.acquire(make_trace(agent_id="y", turn=i))
    traces = mstore.load_traces("y")
    assert len(traces) >= 2  # at least 2 overflows went to episodic

def test_manager_compile_context_returns_agent_context():
    from nexus.core.models import AgentContext
    manager, _ = _build_manager(capacity=5)
    ctx = manager.compile_context("z", "s", [])
    assert isinstance(ctx, AgentContext)
