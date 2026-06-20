from __future__ import annotations
from typing import Tuple, TYPE_CHECKING
from nexus.core.config import SETTINGS
from nexus.core.utils import levenshtein, cosine

if TYPE_CHECKING:
    from nexus.core.models import Entity


def resolve(name: str, kg, embedder) -> Tuple["Entity", float]:
    """Confidence ladder. Never auto-merges below the configured threshold."""
    key = name.strip().lower()

    # 1. exact canonical match
    if key in kg.by_canon:
        return kg.entities[kg.by_canon[key]], 1.0
    # 2. alias match
    if key in kg.by_alias:
        return kg.entities[kg.by_alias[key]], 0.95
    # 3. fuzzy (edit distance <= 2)
    for ent in kg.all_entities():
        if levenshtein(key, ent.canonical_name.lower()) <= 2:
            return ent, 0.80
    # 4. embedding similarity
    qv = embedder.encode(name)
    best, best_sim = None, 0.0
    for ent in kg.all_entities():
        if ent.embedding:
            sim = cosine(qv, ent.embedding)
            if sim > best_sim:
                best, best_sim = ent, sim
    if best and best_sim >= SETTINGS.embedding_sim_threshold:
        return best, 0.75
    # 5. no confident match -> create new, flagged (confidence 0.0)
    return kg.create_entity(name), 0.0
