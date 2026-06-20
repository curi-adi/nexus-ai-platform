from __future__ import annotations
from typing import Dict, List, Optional, Set
from nexus.core.models import KnowledgeChunk, MemoryTrace


class MetadataStore:
    """In-memory prototype backed by dicts + checksum set for dedup."""

    def __init__(self, path: str = ":memory:") -> None:
        self._chunks: Dict[str, KnowledgeChunk] = {}
        self._checksums: Set[str] = set()
        self._traces: List[MemoryTrace] = []

    def insert_chunk(self, chunk: KnowledgeChunk) -> bool:
        """Insert chunk; returns False if checksum duplicate."""
        if not chunk.checksum:
            chunk.finalize()
        if chunk.checksum in self._checksums:
            return False
        self._chunks[chunk.id] = chunk
        self._checksums.add(chunk.checksum)
        return True

    def get_chunks(self, ids: List[str]) -> List[KnowledgeChunk]:
        """Return chunks for the given ids; unknown ids are skipped."""
        return [self._chunks[cid] for cid in ids if cid in self._chunks]

    def all_chunks(self) -> List[KnowledgeChunk]:
        return list(self._chunks.values())

    def save_trace(self, trace: MemoryTrace) -> None:
        self._traces.append(trace)

    def load_traces(self, agent_id: str, only_uncompressed: bool = False) -> List[MemoryTrace]:
        traces = [t for t in self._traces if t.agent_id == agent_id]
        if only_uncompressed:
            traces = [t for t in traces if t.compressed_into is None]
        return traces

    def mark_compressed(self, trace_ids: List[str], summary_chunk_id: str) -> None:
        id_set = set(trace_ids)
        for t in self._traces:
            if t.id in id_set:
                t.compressed_into = summary_chunk_id
