from __future__ import annotations
from typing import List, Tuple
from nexus.core.models import (
    AgentContext, MemoryTrace, RetrievalRequest, RetrievalResult,
    RetrievalStrategy, AccessClaim,
)


class MemoryManager:
    def __init__(self, working, episodic, semantic, retriever):
        self.working = working
        self.episodic = episodic
        self.semantic = semantic
        self.retriever = retriever

    def acquire(self, trace: MemoryTrace) -> None:
        evicted = self.working.push(trace)
        if evicted:
            self.episodic.store(evicted)
        if self.episodic.should_compress(trace.agent_id):
            self.episodic.compress(trace.agent_id)

    def retrieve(
        self,
        req: RetrievalRequest,
        claim: AccessClaim,
    ) -> Tuple[RetrievalStrategy, List[RetrievalResult]]:
        return self.retriever.search(req, claim)

    def compile_context(
        self,
        agent_id: str,
        session_id: str,
        results: List[RetrievalResult],
    ) -> AgentContext:
        return AgentContext(
            agent_id=agent_id,
            session_id=session_id,
            working_memory=self.working.all(),
            retrieved_knowledge=results,
            active_entities=[e for r in results for e in r.chunk.entity_refs],
        )
