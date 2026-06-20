"""
NEXUS Web UI server.

Install:  pip install fastapi uvicorn
Run:      uvicorn app:app --reload  (or: python -m uvicorn app:app --reload)
Then open: http://localhost:8000
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from typing import Dict, List
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel as _Base

from nexus.core.config import SETTINGS
from nexus.core.models import (
    DataDomain, SensitivityLevel, AccessClaim,
    RetrievalRequest,
)
from nexus.embeddings.embedder import get_embedder
from nexus.storage.vector_store import InMemoryVectorStore
from nexus.storage.metadata_store import MetadataStore
from nexus.storage.audit import AuditLog
from nexus.graph.knowledge_graph import KnowledgeGraph
from nexus.retrieval.sparse import BM25Index
from nexus.retrieval.retriever import HybridRetriever
from nexus.governance.provenance import ProvenanceStore
from nexus.memory.working import WorkingMemory
from nexus.memory.episodic import EpisodicMemory, extractive
from nexus.memory.semantic import SemanticMemory
from nexus.memory.manager import MemoryManager
from nexus.agents.base import ExtractiveAgent
import nexus.seed_data as seed_data


# ── Build NEXUS once at startup ───────────────────────────────────
print("NEXUS: initialising...")
embedder = get_embedder()
vstore   = InMemoryVectorStore()
mstore   = MetadataStore()
kg       = KnowledgeGraph()
audit    = AuditLog()
bm25     = BM25Index()
prov     = ProvenanceStore()

seed_data.build(embedder, vstore, mstore, kg)
for c in mstore.all_chunks():
    bm25.add(c.id, c.content)

known_names: set = set()
for e in kg.all_entities():
    known_names.add(e.canonical_name.lower())
    for a in e.aliases:
        known_names.add(a.lower())

retriever = HybridRetriever(bm25, embedder, vstore, mstore, kg, audit, known_names)
semantic  = SemanticMemory(embedder, vstore, mstore)
episodic  = EpisodicMemory(mstore, semantic, prov, summariser=extractive)

def _make_agent(aid: str, sid: str, claim: AccessClaim) -> ExtractiveAgent:
    mem = MemoryManager(WorkingMemory(SETTINGS.working_capacity), episodic, semantic, retriever)
    return ExtractiveAgent(aid, sid, mem, claim)

all_domains = list(DataDomain)
claims: Dict[str, AccessClaim] = {
    "A": AccessClaim(
        principal_id="A", domains=all_domains,
        max_sensitivity=SensitivityLevel.RESTRICTED,
        attributes={"jurisdiction": "*"},
    ),
    "B": AccessClaim(
        principal_id="B",
        domains=[DataDomain.SPORTS, DataDomain.PRODUCT, DataDomain.COMPLIANCE],
        max_sensitivity=SensitivityLevel.INTERNAL,
        attributes={"jurisdiction": "CA"},
    ),
}
agents: Dict[str, ExtractiveAgent] = {
    "A": _make_agent("agentA", "s1", claims["A"]),
    "B": _make_agent("agentB", "s2", claims["B"]),
}

print(f"NEXUS: ready — {len(mstore.all_chunks())} chunks, {len(kg.all_entities())} entities, embedder={embedder.model_id}")


# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(title="NEXUS")

os.makedirs("static", exist_ok=True)


class QueryReq(_Base):
    query: str
    agent_id: str = "A"


@app.post("/api/query")
def run_query(req: QueryReq):
    agent = agents.get(req.agent_id)
    if not agent:
        return {"error": "Unknown agent"}

    answer = agent.think(req.query)

    strat   = retriever.last_strategy
    results = retriever.last_results
    excluded = retriever.last_excluded

    chunks_out = []
    for r in results:
        chunks_out.append({
            "id": r.chunk.id,
            "content": r.chunk.content[:300],
            "domain": r.chunk.domain.value,
            "sensitivity": r.chunk.sensitivity.value,
            "score": round(r.score, 4),
            "explanation": r.explanation,
            "entity_refs": r.chunk.entity_refs,
        })

    ep_traces  = mstore.load_traces(f"agent{req.agent_id}")
    compressed = [t for t in ep_traces if t.compressed_into is not None]
    wm_count   = len(agent.memory.working.all())

    return {
        "strategy":      strat.value if strat else "HYBRID",
        "chunks":        chunks_out,
        "answer":        answer,
        "excluded_count": excluded,
        "memory": {
            "working_count":       wm_count,
            "working_capacity":    SETTINGS.working_capacity,
            "episodic_total":      len(ep_traces),
            "episodic_compressed": len(compressed),
        },
    }


@app.get("/api/graph")
def get_graph():
    entities = [
        {
            "id":   e.id,
            "name": e.canonical_name,
            "type": e.entity_type.value,
            "domain": e.domain.value if e.domain else None,
        }
        for e in kg.all_entities()
    ]
    relationships = [
        {
            "source": r.source_entity_id,
            "target": r.target_entity_id,
            "type":   r.relation_type,
        }
        for r in kg.all_relationships()
    ]
    return {"entities": entities, "relationships": relationships}


@app.get("/api/audit")
def get_audit():
    log = audit.dump()
    return {"entries": log, "total": len(log)}


@app.get("/api/info")
def get_info():
    return {
        "chunks":   len(mstore.all_chunks()),
        "entities": len(kg.all_entities()),
        "embedder": embedder.model_id,
        "agents": {
            "A": {"label": "Full Access",  "sensitivity": "RESTRICTED", "jurisdiction": "Global"},
            "B": {"label": "CA Analyst",   "sensitivity": "INTERNAL",   "jurisdiction": "CA only"},
        },
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
