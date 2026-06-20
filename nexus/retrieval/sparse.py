from __future__ import annotations
import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from nexus.core.utils import tokenize


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs: Dict[str, Counter] = {}      # chunk_id -> term freqs
        self.doc_len: Dict[str, int] = {}
        self.df: Counter = Counter()            # term -> #docs containing it
        self.N = 0
        self.avgdl = 0.0

    def add(self, chunk_id: str, text: str) -> None:
        toks = tokenize(text)
        tf = Counter(toks)
        self.docs[chunk_id] = tf
        self.doc_len[chunk_id] = len(toks)
        for term in tf:
            self.df[term] += 1
        self.N = len(self.docs)
        self.avgdl = sum(self.doc_len.values()) / self.N if self.N else 0.0

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log((self.N - n + 0.5) / (n + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        scores: Dict[str, float] = defaultdict(float)
        for term in tokenize(query):
            if term not in self.df:
                continue
            idf = self._idf(term)
            for cid, tf in self.docs.items():
                f = tf.get(term, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[cid] / self.avgdl)
                scores[cid] += idf * (f * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]
