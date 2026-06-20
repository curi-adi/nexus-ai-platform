from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from nexus.core.models import Entity, Relationship


class KnowledgeGraph:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}             # id -> Entity
        self.by_canon: Dict[str, str] = {}                # canonical_name -> id
        self.by_alias: Dict[str, str] = {}                # alias -> id
        self.adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)  # id -> [(nbr,w)]
        self._rels: List[Relationship] = []

    def upsert_entity(self, e: Entity) -> Entity:
        self.entities[e.id] = e
        self.by_canon[e.canonical_name.lower()] = e.id
        for a in e.aliases:
            self.by_alias[a.lower()] = e.id
        return e

    def upsert_relationship(self, r: Relationship) -> None:
        self.adj[r.source_entity_id].append((r.target_entity_id, r.weight))
        self.adj[r.target_entity_id].append((r.source_entity_id, r.weight))  # undirected traversal
        self._rels.append(r)

    def all_entities(self) -> List[Entity]:
        return list(self.entities.values())

    def all_relationships(self) -> List[Relationship]:
        return list(self._rels)

    def neighbors(self, seed_ids: List[str], max_hops: int, degree_cap: int) -> Dict[str, int]:
        """BFS returning {entity_id: hop_distance}. Expands top-`degree_cap` edges by weight."""
        dist: Dict[str, int] = {s: 0 for s in seed_ids if s in self.entities}
        q: deque = deque(dist.keys())
        while q:
            cur = q.popleft()
            if dist[cur] >= max_hops:
                continue
            top = sorted(self.adj[cur], key=lambda nw: nw[1], reverse=True)[:degree_cap]
            for nbr, _w in top:
                if nbr not in dist:
                    dist[nbr] = dist[cur] + 1
                    q.append(nbr)
        return dist

    def create_entity(self, name: str, entity_type=None) -> Entity:
        from nexus.core.models import EntityType
        e = Entity(
            name=name,
            canonical_name=name,
            entity_type=entity_type or EntityType.CHUNK,
            confidence=0.0,
        )
        return self.upsert_entity(e)
