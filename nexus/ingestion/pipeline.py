from __future__ import annotations
from typing import List, Set
from nexus.core.models import KnowledgeChunk, DataDomain, SensitivityLevel
from nexus.core.utils import extract_entities
from nexus.ingestion.chunker import chunk_text
from nexus.ingestion import pii
from nexus.graph.entity_resolution import resolve


def ingest(
    text: str,
    domain: DataDomain,
    collection: str,
    embedder,
    vstore,
    mstore,
    kg,
    prov,
    known_names: Set[str],
    *,
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL,
    source_uri: str = "",
) -> List[KnowledgeChunk]:
    stored: List[KnowledgeChunk] = []

    for piece in chunk_text(text):
        c = KnowledgeChunk(
            content=piece,
            domain=domain,
            collection=collection,
            sensitivity=sensitivity,
            source_uri=source_uri,
        ).finalize()

        if pii.scan(piece):
            c.sensitivity = SensitivityLevel.RESTRICTED

        rec = prov.record(
            entity_id=c.id,
            activity="ingest",
            agent="pipeline",
            used=[source_uri] if source_uri else [],
            generated=[c.id],
        )
        c.provenance_id = rec.id

        if not mstore.insert_chunk(c):
            continue  # exact duplicate — skip

        c.embedding = embedder.encode(piece)
        vstore.upsert(c.id, c.embedding, collection)

        for name in extract_entities(piece, known_names):
            ent, _conf = resolve(name, kg, embedder)
            if c.id not in ent.source_chunks:
                ent.source_chunks.append(c.id)
            if ent.id not in c.entity_refs:
                c.entity_refs.append(ent.id)

        stored.append(c)

    return stored
