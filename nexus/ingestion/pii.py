from __future__ import annotations
import re

_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SSN   = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
_CC    = re.compile(r"\b\d{16}\b")


def scan(text: str) -> bool:
    """Returns True if any PII pattern is detected in text."""
    return bool(
        _EMAIL.search(text)
        or _SSN.search(text)
        or _PHONE.search(text)
        or _CC.search(text)
    )
