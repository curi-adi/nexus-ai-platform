from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from nexus.core.models import (
    AccessClaim, RetrievalRequest, RetrievalResult, RetrievalStrategy,
)
from nexus.core.config import SETTINGS
from nexus.governance.access import permits
from nexus.retrieval.anti_rag import classify
from nexus.retrieval.dense import dense_search
from nexus.retrieval.graph_rag import graph_search
from nexus.retrieval.fusion import rrf


class HybridRetriever:
    def __init__(self, bm25, embedder, vstore, mstore, kg, audit, known_names: Set[str]):
        self.bm25 = bm25
        self.embedder = embedder
        self.vstore = vstore
        self.mstore = mstore
        self.kg = kg
        self.audit = audit
        self.known_names = known_names
        self.last_strategy: Optional[RetrievalStrategy] = None
        self.last_results: List[RetrievalResult] = []
        self.last_excluded: int = 0

    def search(
        self,
        req: RetrievalRequest,
        claim: AccessClaim,
    ) -> Tuple[RetrievalStrategy, List[RetrievalResult]]:

        strat = classify(req.query, self.known_names)

        if strat in (RetrievalStrategy.DIRECT, RetrievalStrategy.STRUCTURED, RetrievalStrategy.CACHED):
            self.audit.record(claim.principal_id, req.query, strat.value, [], 0)
            self.last_strategy = strat
            self.last_results = []
            self.last_excluded = 0
            return strat, []

        dense  = dense_search(req.query, self.embedder, self.vstore, None, req.top_k)
        sparse = self.bm25.search(req.query, req.top_k)
        graph  = (
            graph_search(req.query, self.kg, self.embedder, self.known_names, req.top_k)
            if req.include_graph else []
        )

        def ids(pairs: List[Tuple[str, float]]) -> List[str]:
            return [cid for cid, _ in pairs]

        fused = rrf([ids(dense), ids(sparse), ids(graph)], SETTINGS.rrf_k)

        all_cids = [cid for cid, _ in fused]
        chunks = self.mstore.get_chunks(all_cids)
        chunk_map: Dict[str, "KnowledgeChunk"] = {c.id: c for c in chunks}

        dense_ids  = set(ids(dense))
        sparse_ids = set(ids(sparse))
        graph_ids  = set(ids(graph))

        def contained(cid: str) -> str:
            parts = []
            if cid in dense_ids:  parts.append("dense")
            if cid in sparse_ids: parts.append("sparse")
            if cid in graph_ids:  parts.append("graph")
            return ",".join(parts)

        results: List[RetrievalResult] = []
        excluded = 0
        for cid, score in fused:
            chunk = chunk_map.get(cid)
            if chunk is None:
                continue
            if not permits(claim, chunk):
                excluded += 1
                continue
            results.append(RetrievalResult(
                chunk=chunk,
                score=score,
                strategy=strat,
                explanation=contained(cid),
            ))

        self.audit.record(
            claim.principal_id, req.query, strat.value,
            [r.chunk.id for r in results], excluded,
        )
        final = results[:req.top_k]
        self.last_strategy = strat
        self.last_results = final
        self.last_excluded = excluded
        return strat, final
