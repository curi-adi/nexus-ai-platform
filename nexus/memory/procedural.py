from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional


class ProceduralMemory:
    """In-memory tool registry — stable, manually versioned."""

    def __init__(self):
        self._registry: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._registry[name] = fn

    def get(self, name: str) -> Optional[Callable[..., Any]]:
        return self._registry.get(name)

    def all_names(self) -> List[str]:
        return list(self._registry.keys())
