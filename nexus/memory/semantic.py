from __future__ import annotations
from typing import List
from nexus.core.models import KnowledgeChunk


class SemanticMemory:
    """Wrapper around embedder + vector store + metadata store for semantic tier."""

    def __init__(self, embedder, vstore, mstore):
        self.embedder = embedder
        self.vstore = vstore
        self.mstore = mstore

    def store(self, chunk: KnowledgeChunk) -> None:
        """Embed if needed, then upsert into vector store and metadata store."""
        if chunk.embedding is None:
            chunk.embedding = self.embedder.encode(chunk.content)
        self.vstore.upsert(chunk.id, chunk.embedding, chunk.collection)
        self.mstore.insert_chunk(chunk)

    def active_entities(self, chunk_ids: List[str]) -> List[str]:
        """Return all entity IDs referenced by the given chunks."""
        chunks = self.mstore.get_chunks(chunk_ids)
        entities: List[str] = []
        for c in chunks:
            entities.extend(c.entity_refs)
        seen = set()
        result = []
        for e in entities:
            if e not in seen:
                seen.add(e)
                result.append(e)
        return result
