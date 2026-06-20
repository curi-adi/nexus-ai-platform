from __future__ import annotations
from typing import List


def chunk_text(text: str, target_tokens: int = 512, overlap: float = 0.2) -> List[str]:
    """RECURSIVE chunker: paragraph-aware with sliding overlap."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    overlap_tokens = int(target_tokens * overlap)

    chunks: List[str] = []
    current_tokens: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_tokens = para.split()
        # If a single paragraph exceeds target, hard-split it on word boundary
        if len(para_tokens) > target_tokens:
            if current_tokens:
                chunks.append(" ".join(current_tokens))
                current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens else []
                current_len = len(current_tokens)
            i = 0
            while i < len(para_tokens):
                segment = para_tokens[i : i + target_tokens]
                chunks.append(" ".join(segment))
                i += target_tokens - overlap_tokens
            continue

        if current_len + len(para_tokens) > target_tokens and current_tokens:
            chunks.append(" ".join(current_tokens))
            current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens else []
            current_len = len(current_tokens)

        current_tokens.extend(para_tokens)
        current_len += len(para_tokens)

    if current_tokens:
        chunks.append(" ".join(current_tokens))

    return chunks
