from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib, uuid
from pydantic import BaseModel, Field


def _uid() -> str: return uuid.uuid4().hex
def _now() -> datetime: return datetime.now(timezone.utc)


class SensitivityLevel(str, Enum):
    PUBLIC = "PUBLIC"; INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"; RESTRICTED = "RESTRICTED"

class DataDomain(str, Enum):
    CUSTOMER="CUSTOMER"; PRODUCT="PRODUCT"; MARKETING="MARKETING"; ENGINEERING="ENGINEERING"
    OPERATIONS="OPERATIONS"; COMPLIANCE="COMPLIANCE"; SPORTS="SPORTS"; FINANCE="FINANCE"

class RetrievalStrategy(str, Enum):
    DENSE="DENSE"; SPARSE="SPARSE"; HYBRID="HYBRID"; GRAPH="GRAPH"
    DIRECT="DIRECT"; STRUCTURED="STRUCTURED"; CACHED="CACHED"

class EntityType(str, Enum):
    PLAYER="PLAYER"; TEAM="TEAM"; LEAGUE="LEAGUE"; EVENT="EVENT"; MARKET="MARKET"
    PRODUCT="PRODUCT"; CUSTOMER="CUSTOMER"; POLICY="POLICY"; REGULATION="REGULATION"
    JURISDICTION="JURISDICTION"; CHUNK="CHUNK"


class KnowledgeChunk(BaseModel):
    id: str = Field(default_factory=_uid)
    content: str
    domain: DataDomain
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    source_uri: str = ""
    collection: str = "default"
    embedding: Optional[List[float]] = None
    entity_refs: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance_id: Optional[str] = None
    checksum: str = ""
    token_count: int = 0

    def finalize(self) -> "KnowledgeChunk":
        """Compute checksum + token_count. Call once after content is set."""
        self.checksum = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        self.token_count = len(self.content.split())
        return self


class Entity(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    entity_type: EntityType
    canonical_name: str
    aliases: List[str] = Field(default_factory=list)
    domain: Optional[DataDomain] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    source_chunks: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None


class Relationship(BaseModel):
    id: str = Field(default_factory=_uid)
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    weight: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class MemoryTrace(BaseModel):
    id: str = Field(default_factory=_uid)
    agent_id: str
    session_id: str
    turn_index: int
    role: str                              # "user" | "assistant"
    content: str
    retrieved_chunks: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)
    compressed_into: Optional[str] = None


class AccessClaim(BaseModel):
    principal_id: str
    principal_type: str = "agent"
    domains: List[DataDomain] = Field(default_factory=list)
    max_sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    collections: List[str] = Field(default_factory=list)   # empty = all
    attributes: Dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str
    agent_id: str = ""
    session_id: str = ""
    collections: Optional[List[str]] = None
    top_k: int = 10
    include_graph: bool = True


class RetrievalResult(BaseModel):
    chunk: KnowledgeChunk
    score: float
    strategy: RetrievalStrategy
    explanation: str = ""
    hop_path: Optional[List[str]] = None


class ProvenanceRecord(BaseModel):
    id: str = Field(default_factory=_uid)
    entity_id: str
    activity: str
    agent: str
    used: List[str] = Field(default_factory=list)
    generated: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)


class AgentContext(BaseModel):
    agent_id: str
    session_id: str
    working_memory: List[MemoryTrace] = Field(default_factory=list)
    retrieved_knowledge: List[RetrievalResult] = Field(default_factory=list)
    active_entities: List[str] = Field(default_factory=list)
    retrieval_strategy_used: Optional[RetrievalStrategy] = None

    def context_string(self, max_trace_chars: int = 200, max_chunk_chars: int = 400) -> str:
        """Flatten into the text block handed to the LLM (token-budgeted)."""
        parts = []
        for t in self.working_memory[-5:]:
            content = t.content[:max_trace_chars] + ("..." if len(t.content) > max_trace_chars else "")
            parts.append(f"{t.role}: {content}")
        for r in self.retrieved_knowledge:
            content = r.chunk.content[:max_chunk_chars] + ("..." if len(r.chunk.content) > max_chunk_chars else "")
            parts.append(f"[{r.chunk.domain.value}] {content}")
        return "\n".join(parts)
