from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple


def rrf(ranked_lists: List[List[str]], k: int = 60) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion. Input: each list is chunk_ids best-first."""
    scores: Dict[str, float] = defaultdict(float)
    for lst in ranked_lists:
        for rank, cid in enumerate(lst):
            scores[cid] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
