from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from nexus.core.utils import cosine


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunk_id: str, vector: List[float], collection: str) -> None: ...
    @abstractmethod
    def search(
        self,
        vector: List[float],
        collection: Optional[str],
        top_k: int,
    ) -> List[Tuple[str, float]]: ...


class InMemoryVectorStore(VectorStore):
    """Brute-force cosine. O(n) per query — fine at demo scale."""
    def __init__(self):
        self.data: Dict[str, Dict[str, List[float]]] = {}   # collection -> {id: vec}

    def upsert(self, chunk_id: str, vector: List[float], collection: str) -> None:
        self.data.setdefault(collection, {})[chunk_id] = vector

    def search(
        self,
        vector: List[float],
        collection: Optional[str],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        if collection is None:                       # search across all collections
            items = {cid: v for col in self.data.values() for cid, v in col.items()}
        else:
            items = self.data.get(collection, {})
        scored = [(cid, cosine(vector, v)) for cid, v in items.items()]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]
