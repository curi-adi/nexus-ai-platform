from __future__ import annotations
import hashlib, math, re
from typing import List, Set


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric word tokens. The single text-splitting primitive."""
    return re.findall(r"[a-z0-9]+", text.lower())


def stable_hash(token: str) -> int:
    """Deterministic across processes (unlike built-in hash())."""
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)


def l2_normalize(v: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm > 0 else v


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b: return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def levenshtein(a: str, b: str) -> int:
    """Edit distance via DP. O(len(a)*len(b))."""
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def extract_entities(text: str, known_names: Set[str]) -> List[str]:
    """The known entity names/aliases that appear in `text` (word-boundary match)."""
    low = text.lower()
    found = []
    for name in known_names:
        if re.search(r"\b" + re.escape(name.lower()) + r"\b", low):
            found.append(name)
    return found
