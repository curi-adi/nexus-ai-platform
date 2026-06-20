from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any


class AuditLog:
    """Append-only log of every retrieval decision. Never updates or deletes."""

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record(
        self,
        principal_id: str,
        query: str,
        strategy: str,
        returned_ids: List[str],
        excluded_count: int,
    ) -> None:
        seq = len(self.entries) + 1
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
        self.entries.append({
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "principal_id": principal_id,
            "query_hash": query_hash,
            "strategy": strategy,
            "returned_ids": returned_ids,
            "excluded_count": excluded_count,
        })

    def dump(self) -> List[Dict[str, Any]]:
        return list(self.entries)
