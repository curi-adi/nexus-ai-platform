from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from nexus.eval.metrics import recall_at_k, mrr, ndcg_at_k
from nexus.core.models import RetrievalRequest, AccessClaim


class GoldenSet:
    """Hold (query -> set of relevant chunk_ids) pairs and run eval metrics."""

    def __init__(self, pairs: Optional[List[Tuple[str, Set[str]]]] = None):
        self.pairs: List[Tuple[str, Set[str]]] = pairs or []

    def add(self, query: str, relevant_ids: Set[str]) -> None:
        self.pairs.append((query, relevant_ids))

    def run(self, retriever, claim: AccessClaim, k: int = 10) -> Dict[str, float]:
        if not self.pairs:
            return {}

        total_recall = total_mrr = total_ndcg = 0.0
        for query, relevant in self.pairs:
            req = RetrievalRequest(query=query, top_k=k)
            _strat, results = retriever.search(req, claim)
            retrieved_ids = [r.chunk.id for r in results]
            total_recall += recall_at_k(retrieved_ids, relevant, k)
            total_mrr    += mrr(retrieved_ids, relevant)
            total_ndcg   += ndcg_at_k(retrieved_ids, relevant, k)

        n = len(self.pairs)
        return {
            f"recall@{k}": total_recall / n,
            "mrr":         total_mrr / n,
            f"ndcg@{k}":   total_ndcg / n,
        }

    def gate(self, retriever, claim: AccessClaim, k: int = 10, threshold: float = 0.9) -> bool:
        """CI gate: True if recall@k >= threshold."""
        metrics = self.run(retriever, claim, k)
        return metrics.get(f"recall@{k}", 0.0) >= threshold
