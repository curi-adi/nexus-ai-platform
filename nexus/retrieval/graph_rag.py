from __future__ import annotations
from typing import Dict, List, Set, Tuple
from nexus.core.config import SETTINGS
from nexus.core.utils import extract_entities
from nexus.graph.entity_resolution import resolve


def graph_search(
    query: str,
    kg,
    embedder,
    known_names: Set[str],
    top_k: int,
) -> List[Tuple[str, float]]:
    """Multi-hop graph retrieval. Returns (chunk_id, score) pairs."""
    names = extract_entities(query, known_names)
    if not names:
        return []

    seed_ids: List[str] = []
    for name in names:
        ent, _conf = resolve(name, kg, embedder)
        seed_ids.append(ent.id)

    if not seed_ids:
        return []

    dist: Dict[str, int] = kg.neighbors(seed_ids, SETTINGS.max_hops, SETTINGS.degree_cap)

    chunk_scores: Dict[str, float] = {}
    for eid, hop in dist.items():
        entity = kg.entities.get(eid)
        if entity is None:
            continue
        score = 1.0 / (1.0 + hop)
        for cid in entity.source_chunks:
            if cid not in chunk_scores or score > chunk_scores[cid]:
                chunk_scores[cid] = score

    ranked = sorted(chunk_scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:top_k]
