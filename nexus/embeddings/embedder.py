from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from nexus.core.utils import tokenize, stable_hash, l2_normalize


class Embedder(ABC):
    @abstractmethod
    def encode(self, text: str) -> List[float]: ...
    def encode_many(self, texts: List[str]) -> List[List[float]]:
        return [self.encode(t) for t in texts]
    @property
    @abstractmethod
    def model_id(self) -> str: ...


class HashingEmbedder(Embedder):
    """Stdlib fallback: hashed bag-of-words → fixed-dim L2-normalised vector."""
    def __init__(self, dim: int = 256): self.dim = dim
    def encode(self, text: str) -> List[float]:
        v = [0.0] * self.dim
        for tok in tokenize(text):
            v[stable_hash(tok) % self.dim] += 1.0
        return l2_normalize(v)
    @property
    def model_id(self) -> str: return f"hashing-{self.dim}"


class LocalEmbedder(Embedder):
    def __init__(self, model): self.model = model
    def encode(self, text: str) -> List[float]:
        return l2_normalize(list(self.model.encode(text)))
    @property
    def model_id(self) -> str: return "all-MiniLM-L6-v2"


def get_embedder() -> Embedder:
    try:
        from sentence_transformers import SentenceTransformer
        return LocalEmbedder(SentenceTransformer("all-MiniLM-L6-v2"))
    except Exception:
        return HashingEmbedder()
