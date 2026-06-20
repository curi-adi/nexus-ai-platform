from __future__ import annotations
from typing import List, Optional, Tuple


def dense_search(
    query: str,
    embedder,
    vstore,
    collection: Optional[str],
    top_k: int,
) -> List[Tuple[str, float]]:
    """Embed query and search the vector store. Returns (chunk_id, score) pairs."""
    return vstore.search(embedder.encode(query), collection, top_k)
