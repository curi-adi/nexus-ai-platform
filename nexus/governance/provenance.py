from __future__ import annotations
from typing import List, Optional
from nexus.core.models import ProvenanceRecord


class ProvenanceStore:
    def __init__(self):
        self._records: List[ProvenanceRecord] = []

    def record(
        self,
        entity_id: str,
        activity: str,
        agent: str,
        used: Optional[List[str]] = None,
        generated: Optional[List[str]] = None,
    ) -> ProvenanceRecord:
        rec = ProvenanceRecord(
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            used=used or [],
            generated=generated or [],
        )
        self._records.append(rec)
        return rec

    def get(self, entity_id: str) -> List[ProvenanceRecord]:
        return [r for r in self._records if r.entity_id == entity_id]

    def all(self) -> List[ProvenanceRecord]:
        return list(self._records)
