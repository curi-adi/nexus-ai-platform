from __future__ import annotations
from collections import deque
from typing import List, Optional
from nexus.core.models import MemoryTrace


class WorkingMemory:
    def __init__(self, capacity: int = 10):
        self.buf: deque = deque(maxlen=capacity)

    def push(self, trace: MemoryTrace) -> Optional[MemoryTrace]:
        """Append; return the trace evicted by overflow, if any."""
        evicted = self.buf[0] if len(self.buf) == self.buf.maxlen else None
        self.buf.append(trace)        # deque(maxlen) auto-drops the left item
        return evicted

    def all(self) -> List[MemoryTrace]:
        return list(self.buf)
