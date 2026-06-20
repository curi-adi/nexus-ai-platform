"""Tests for KnowledgeGraph BFS and entity resolution confidence ladder."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nexus.graph.knowledge_graph import KnowledgeGraph
from nexus.graph.entity_resolution import resolve
from nexus.embeddings.embedder import HashingEmbedder
from nexus.core.models import Entity, Relationship, EntityType


def _chain_graph():
    """Build A-B-C chain."""
    kg = KnowledgeGraph()
    a = Entity(name="A", canonical_name="A", entity_type=EntityType.PLAYER)
    b = Entity(name="B", canonical_name="B", entity_type=EntityType.TEAM)
    c = Entity(name="C", canonical_name="C", entity_type=EntityType.LEAGUE)
    for e in [a, b, c]:
        kg.upsert_entity(e)
    kg.upsert_relationship(Relationship(source_entity_id=a.id, target_entity_id=b.id, relation_type="PLAYS_FOR"))
    kg.upsert_relationship(Relationship(source_entity_id=b.id, target_entity_id=c.id, relation_type="COMPETES_IN"))
    return kg, a, b, c


# ── neighbors / BFS ───────────────────────────────────────────────────────────

def test_neighbors_full_chain():
    kg, a, b, c = _chain_graph()
    dist = kg.neighbors([a.id], max_hops=2, degree_cap=8)
    assert dist[a.id] == 0
    assert dist[b.id] == 1
    assert dist[c.id] == 2

def test_neighbors_hop_cap_excludes_far_node():
    kg, a, b, c = _chain_graph()
    dist = kg.neighbors([a.id], max_hops=1, degree_cap=8)
    assert a.id in dist
    assert b.id in dist
    assert c.id not in dist

def test_neighbors_empty_seeds():
    kg, a, b, c = _chain_graph()
    dist = kg.neighbors([], max_hops=3, degree_cap=8)
    assert dist == {}

def test_neighbors_degree_cap():
    """Degree cap limits fan-out per node."""
    kg = KnowledgeGraph()
    hub = Entity(name="hub", canonical_name="hub", entity_type=EntityType.PLAYER)
    kg.upsert_entity(hub)
    leaves = []
    for i in range(10):
        leaf = Entity(name=f"leaf{i}", canonical_name=f"leaf{i}", entity_type=EntityType.TEAM)
        kg.upsert_entity(leaf)
        kg.upsert_relationship(Relationship(
            source_entity_id=hub.id, target_entity_id=leaf.id, relation_type="PLAYS_FOR", weight=float(i),
        ))
        leaves.append(leaf)

    dist = kg.neighbors([hub.id], max_hops=1, degree_cap=3)
    reached_leaves = [eid for eid in dist if eid != hub.id]
    assert len(reached_leaves) == 3   # capped at degree_cap


# ── Entity resolution confidence ladder ──────────────────────────────────────

def _seeded_kg():
    kg = KnowledgeGraph()
    embedder = HashingEmbedder()
    mahomes = Entity(
        name="Patrick Mahomes",
        canonical_name="Patrick Mahomes",
        entity_type=EntityType.PLAYER,
        aliases=["P. Mahomes", "Mahomes"],
        embedding=embedder.encode("Patrick Mahomes"),
    )
    kg.upsert_entity(mahomes)
    return kg, embedder, mahomes

def test_resolve_exact_canonical():
    kg, embedder, mahomes = _seeded_kg()
    ent, conf = resolve("Patrick Mahomes", kg, embedder)
    assert ent.id == mahomes.id
    assert conf == 1.0

def test_resolve_alias():
    kg, embedder, mahomes = _seeded_kg()
    ent, conf = resolve("P. Mahomes", kg, embedder)
    assert ent.id == mahomes.id
    assert conf == 0.95

def test_resolve_typo_fuzzy():
    kg, embedder, mahomes = _seeded_kg()
    ent, conf = resolve("Patrik Mahomes", kg, embedder)  # 1-edit typo
    assert ent.id == mahomes.id
    assert conf == 0.80

def test_resolve_unknown_creates_new_node():
    kg, embedder, _ = _seeded_kg()
    initial_count = len(kg.all_entities())
    ent, conf = resolve("Zxqw123NoMatch", kg, embedder)
    assert conf == 0.0
    assert len(kg.all_entities()) == initial_count + 1
