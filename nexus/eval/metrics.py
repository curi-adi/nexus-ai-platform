from __future__ import annotations
import math
from typing import List, Set


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    if not relevant: return 0.0
    hit = len(set(retrieved[:k]) & relevant)
    return hit / len(relevant)


def mrr(retrieved: List[str], relevant: Set[str]) -> float:
    for i, cid in enumerate(retrieved, 1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    dcg = sum((1.0 / math.log2(i + 2)) for i, cid in enumerate(retrieved[:k]) if cid in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal > 0 else 0.0
