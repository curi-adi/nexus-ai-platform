from __future__ import annotations
from abc import ABC, abstractmethod
from nexus.core.models import MemoryTrace, RetrievalRequest, RetrievalStrategy


class BaseAgent(ABC):
    def __init__(self, agent_id: str, session_id: str, memory, claim):
        self.agent_id, self.session_id = agent_id, session_id
        self.memory, self.claim = memory, claim
        self._turn = 0

    def think(self, user_input: str) -> str:
        self._turn += 1
        self.memory.acquire(MemoryTrace(
            agent_id=self.agent_id,
            session_id=self.session_id,
            turn_index=self._turn,
            role="user",
            content=user_input,
        ))
        strat, results = self.memory.retrieve(
            RetrievalRequest(
                query=user_input,
                agent_id=self.agent_id,
                session_id=self.session_id,
            ),
            self.claim,
        )
        ctx = self.memory.compile_context(self.agent_id, self.session_id, results)
        ctx.retrieval_strategy_used = strat
        answer = self._call_llm(ctx.context_string(), user_input, strat)
        self._turn += 1
        self.memory.acquire(MemoryTrace(
            agent_id=self.agent_id,
            session_id=self.session_id,
            turn_index=self._turn,
            role="assistant",
            content=answer,
        ))
        return answer

    @abstractmethod
    def _call_llm(self, context: str, query: str, strategy: RetrievalStrategy) -> str: ...


class ExtractiveAgent(BaseAgent):
    """Offline default: answers by quoting retrieved context. No API key needed."""
    def _call_llm(self, context: str, query: str, strategy: RetrievalStrategy) -> str:
        if strategy == RetrievalStrategy.DIRECT:
            return "(general knowledge — no retrieval needed; an LLM answers here)"
        if strategy == RetrievalStrategy.STRUCTURED:
            return "(routed to a live/structured source, not the knowledge store)"
        if not context.strip():
            return "I don't have grounded knowledge to answer that."
        return f"Based on retrieved context:\n{context}"


class ClaudeAgent(BaseAgent):
    """LLM-backed agent using the Anthropic API. Falls back to ExtractiveAgent."""

    def __init__(self, agent_id: str, session_id: str, memory, claim, model: str = "claude-sonnet-4-6"):
        super().__init__(agent_id, session_id, memory, claim)
        self.model = model
        self._client = None
        try:
            import anthropic
            self._client = anthropic.Anthropic()
        except Exception:
            pass

    def _call_llm(self, context: str, query: str, strategy: RetrievalStrategy) -> str:
        if strategy == RetrievalStrategy.DIRECT:
            return "(general knowledge — no retrieval needed)"
        if strategy == RetrievalStrategy.STRUCTURED:
            return "(routed to a live/structured source)"

        if self._client is None:
            if not context.strip():
                return "I don't have grounded knowledge to answer that."
            return f"Based on retrieved context:\n{context}"

        system = (
            "You are a helpful assistant with access to a curated knowledge base. "
            "Answer the user's question based ONLY on the provided context. "
            "If the context doesn't contain the answer, say so.\n\n"
            f"CONTEXT:\n{context}"
        )
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": query}],
        )
        return msg.content[0].text
