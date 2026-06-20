from __future__ import annotations
import re
from typing import Set
from nexus.core.models import RetrievalStrategy as RS

_LIVE    = re.compile(r"\b(live|right now|current|currently|today|balance|odds now)\b", re.I)
_GENERAL = re.compile(r"\b(what is|define|explain|how do|formula for)\b", re.I)


def _entity_count(query: str, known_names: Set[str]) -> int:
    q = query.lower()
    return sum(1 for name in known_names if name.lower() in q)


def classify(query: str, known_names: Set[str], cache_hit: bool = False) -> RS:
    if cache_hit:                              return RS.CACHED
    if _LIVE.search(query):                    return RS.STRUCTURED
    if _GENERAL.search(query) and _entity_count(query, known_names) == 0:
        return RS.DIRECT
    if _entity_count(query, known_names) >= 2: return RS.GRAPH
    return RS.HYBRID
