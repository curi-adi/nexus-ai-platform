from __future__ import annotations
import re
from typing import Callable, Optional
from nexus.core.models import KnowledgeChunk, DataDomain, SensitivityLevel
from nexus.core.config import SETTINGS


def extractive(text: str, n: int = 5) -> str:
    """Fallback summariser: return first N sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:n])


class EpisodicMemory:
    def __init__(self, mstore, semantic, prov, summariser: Optional[Callable] = None):
        self.mstore = mstore
        self.semantic = semantic
        self.prov = prov
        self.summariser = summariser or extractive

    def store(self, trace) -> None:
        self.mstore.save_trace(trace)

    def should_compress(self, agent_id: str) -> bool:
        return len(self.mstore.load_traces(agent_id, only_uncompressed=True)) >= SETTINGS.episodic_compress_at

    def compress(self, agent_id: str) -> KnowledgeChunk:
        traces = self.mstore.load_traces(agent_id, only_uncompressed=True)
        text = "\n".join(f"{t.role}: {t.content}" for t in traces)
        summary = self.summariser(text)
        chunk = KnowledgeChunk(
            content=summary,
            domain=DataDomain.OPERATIONS,
            collection="episodic_summaries",
            sensitivity=SensitivityLevel.INTERNAL,
        ).finalize()
        self.semantic.store(chunk)
        self.prov.record(
            entity_id=chunk.id,
            activity="episodic_compression",
            agent=agent_id,
            used=[t.id for t in traces],
            generated=[chunk.id],
        )
        self.mstore.mark_compressed([t.id for t in traces], chunk.id)   # mark, never delete
        return chunk
