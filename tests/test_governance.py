"""Tests for ABAC permits() and audit log."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nexus.governance.access import permits
from nexus.storage.audit import AuditLog
from nexus.core.models import (
    AccessClaim, KnowledgeChunk,
    DataDomain, SensitivityLevel,
)


def make_chunk(sensitivity, domain=DataDomain.COMPLIANCE, metadata=None, collection="default"):
    return KnowledgeChunk(
        content="test",
        domain=domain,
        sensitivity=sensitivity,
        collection=collection,
        metadata=metadata or {},
    ).finalize()


def make_claim(max_sens, domains=None, jurisdiction=None, collections=None):
    attrs = {}
    if jurisdiction:
        attrs["jurisdiction"] = jurisdiction
    return AccessClaim(
        principal_id="test",
        domains=domains or list(DataDomain),
        max_sensitivity=max_sens,
        collections=collections or [],
        attributes=attrs,
    )


# ── Sensitivity ───────────────────────────────────────────────────────────────

def test_restricted_chunk_internal_claim_denied():
    chunk = make_chunk(SensitivityLevel.RESTRICTED)
    claim = make_claim(SensitivityLevel.INTERNAL)
    assert not permits(claim, chunk)

def test_public_chunk_internal_claim_allowed():
    chunk = make_chunk(SensitivityLevel.PUBLIC)
    claim = make_claim(SensitivityLevel.INTERNAL)
    assert permits(claim, chunk)

def test_internal_chunk_internal_claim_allowed():
    chunk = make_chunk(SensitivityLevel.INTERNAL)
    claim = make_claim(SensitivityLevel.INTERNAL)
    assert permits(claim, chunk)

def test_restricted_chunk_restricted_claim_allowed():
    chunk = make_chunk(SensitivityLevel.RESTRICTED)
    claim = make_claim(SensitivityLevel.RESTRICTED)
    assert permits(claim, chunk)


# ── Domain gating ─────────────────────────────────────────────────────────────

def test_wrong_domain_denied():
    chunk = make_chunk(SensitivityLevel.PUBLIC, domain=DataDomain.COMPLIANCE)
    claim = make_claim(SensitivityLevel.PUBLIC, domains=[DataDomain.SPORTS])
    assert not permits(claim, chunk)

def test_correct_domain_allowed():
    chunk = make_chunk(SensitivityLevel.PUBLIC, domain=DataDomain.SPORTS)
    claim = make_claim(SensitivityLevel.PUBLIC, domains=[DataDomain.SPORTS])
    assert permits(claim, chunk)


# ── Jurisdiction gating ───────────────────────────────────────────────────────

def test_nj_chunk_pa_claim_denied():
    chunk = make_chunk(SensitivityLevel.INTERNAL, metadata={"jurisdiction": "NJ"})
    claim = make_claim(SensitivityLevel.INTERNAL, jurisdiction="PA")
    assert not permits(claim, chunk)

def test_nj_chunk_nj_claim_allowed():
    chunk = make_chunk(SensitivityLevel.INTERNAL, metadata={"jurisdiction": "NJ"})
    claim = make_claim(SensitivityLevel.INTERNAL, jurisdiction="NJ")
    assert permits(claim, chunk)

def test_nj_chunk_wildcard_claim_allowed():
    chunk = make_chunk(SensitivityLevel.INTERNAL, metadata={"jurisdiction": "NJ"})
    claim = make_claim(SensitivityLevel.INTERNAL, jurisdiction="*")
    assert permits(claim, chunk)

def test_no_jurisdiction_tag_not_gated():
    chunk = make_chunk(SensitivityLevel.INTERNAL, metadata={})
    claim = make_claim(SensitivityLevel.INTERNAL, jurisdiction="NJ")
    assert permits(claim, chunk)


# ── Collection gating ─────────────────────────────────────────────────────────

def test_collection_gating():
    chunk = make_chunk(SensitivityLevel.PUBLIC, collection="sports")
    claim = make_claim(SensitivityLevel.PUBLIC, collections=["compliance"])
    assert not permits(claim, chunk)

def test_collection_empty_means_all():
    chunk = make_chunk(SensitivityLevel.PUBLIC, collection="sports")
    claim = make_claim(SensitivityLevel.PUBLIC, collections=[])
    assert permits(claim, chunk)


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_two_entries():
    log = AuditLog()
    log.record("A", "query one", "HYBRID", ["id1"], 0)
    log.record("B", "query two", "DIRECT", [], 1)
    entries = log.dump()
    assert len(entries) == 2
    assert entries[0]["seq"] == 1
    assert entries[1]["seq"] == 2

def test_audit_no_raw_query():
    log = AuditLog()
    log.record("X", "secret query", "HYBRID", [], 0)
    entry = log.dump()[0]
    assert "secret query" not in str(entry)

def test_audit_excluded_count():
    log = AuditLog()
    log.record("A", "some query", "HYBRID", ["a", "b"], 3)
    assert log.dump()[0]["excluded_count"] == 3
