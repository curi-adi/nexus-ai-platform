from __future__ import annotations
from nexus.core.models import (
    KnowledgeChunk, Entity, Relationship,
    DataDomain, SensitivityLevel, EntityType,
)


def build(embedder, vstore, mstore, kg) -> None:
    """Populate all stores with the demo knowledge base."""

    # ── Chunks ──────────────────────────────────────────────────────────────
    chunk_rows = [
        dict(
            content="Patrick Mahomes is the active quarterback (QB) for the Kansas City Chiefs. "
                    "He has won multiple NFL MVP awards and Super Bowl championships. "
                    "Mahomes is one of the most marketable athletes in professional sports.",
            domain=DataDomain.SPORTS,
            sensitivity=SensitivityLevel.PUBLIC,
            metadata={},
        ),
        dict(
            content="New Jersey (NJ) requires 24-hour advance notice plus a compliance sign-off "
                    "from the legal team before any boosted-odds promotion can be launched. "
                    "Failure to comply may result in fines and suspension of betting operations.",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={"jurisdiction": "NJ"},
        ),
        dict(
            content="Pennsylvania (PA) boosted-odds promotions require a state filing 48 hours "
                    "ahead of the promotion launch. All promotional materials must be pre-approved "
                    "by the Pennsylvania Gaming Control Board.",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={"jurisdiction": "PA"},
        ),
        dict(
            content="The OddsBoost feature supports player-prop markets, game-outcome markets, "
                    "and parlay combinations. Boosts are applied at the bet-slip level and are "
                    "subject to jurisdiction-specific limits and compliance checks.",
            domain=DataDomain.PRODUCT,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={},
        ),
        dict(
            content="Responsible-gaming rules mandate spend limits for all users, self-exclusion "
                    "options accessible at any time, and mandatory cool-down periods after "
                    "loss-limit thresholds are crossed. Violation triggers account suspension.",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={},
        ),
        dict(
            content="INTERNAL — Incident postmortem: payout bug on 2026-03-15. "
                    "Affected customer a@b.com received a duplicate payout. "
                    "Root cause: race condition in settlement worker. Resolved in hotfix v2.3.1.",
            domain=DataDomain.OPERATIONS,
            sensitivity=SensitivityLevel.RESTRICTED,
            metadata={},
        ),
    ]

    stored_chunks: list[KnowledgeChunk] = []
    for row in chunk_rows:
        c = KnowledgeChunk(
            content=row["content"],
            domain=row["domain"],
            sensitivity=row["sensitivity"],
            collection="default",
            metadata=row["metadata"],
        ).finalize()
        c.embedding = embedder.encode(c.content)
        mstore.insert_chunk(c)
        vstore.upsert(c.id, c.embedding, c.collection)
        stored_chunks.append(c)

    sports_chunk = stored_chunks[0]

    # ── Entities ─────────────────────────────────────────────────────────────
    mahomes = Entity(
        name="Patrick Mahomes",
        canonical_name="Patrick Mahomes",
        entity_type=EntityType.PLAYER,
        aliases=["P. Mahomes", "Mahomes"],
        domain=DataDomain.SPORTS,
        properties={"position": "QB", "status": "active"},
        embedding=embedder.encode("Patrick Mahomes"),
    )
    chiefs = Entity(
        name="Kansas City Chiefs",
        canonical_name="Kansas City Chiefs",
        entity_type=EntityType.TEAM,
        aliases=["Chiefs", "KC"],
        domain=DataDomain.SPORTS,
        properties={"city": "Kansas City"},
        embedding=embedder.encode("Kansas City Chiefs"),
    )
    nfl = Entity(
        name="NFL",
        canonical_name="NFL",
        entity_type=EntityType.LEAGUE,
        aliases=["National Football League"],
        domain=DataDomain.SPORTS,
        properties={"sport": "Football"},
        embedding=embedder.encode("NFL"),
    )
    nfl_mvp = Entity(
        name="NFL MVP",
        canonical_name="NFL MVP",
        entity_type=EntityType.MARKET,
        aliases=["Most Valuable Player"],
        domain=DataDomain.SPORTS,
        properties={"type": "futures"},
        embedding=embedder.encode("NFL MVP"),
    )
    boost_policy = Entity(
        name="Boost Policy",
        canonical_name="Boost Policy",
        entity_type=EntityType.POLICY,
        aliases=["OddsBoost Policy"],
        properties={"version": "v4"},
        embedding=embedder.encode("Boost Policy"),
    )
    new_jersey = Entity(
        name="New Jersey",
        canonical_name="New Jersey",
        entity_type=EntityType.JURISDICTION,
        aliases=["NJ"],
        properties={"compliance": "high"},
        embedding=embedder.encode("New Jersey"),
    )
    oddsboost = Entity(
        name="OddsBoost",
        canonical_name="OddsBoost",
        entity_type=EntityType.PRODUCT,
        aliases=["Odds Boost"],
        properties={"version": "3.2"},
        embedding=embedder.encode("OddsBoost"),
    )

    for e in [mahomes, chiefs, nfl, nfl_mvp, boost_policy, new_jersey, oddsboost]:
        kg.upsert_entity(e)

    # ── Relationships ─────────────────────────────────────────────────────────
    rels = [
        Relationship(source_entity_id=mahomes.id,      target_entity_id=chiefs.id,      relation_type="PLAYS_FOR"),
        Relationship(source_entity_id=chiefs.id,       target_entity_id=nfl.id,         relation_type="COMPETES_IN"),
        Relationship(source_entity_id=nfl_mvp.id,      target_entity_id=boost_policy.id, relation_type="GOVERNED_BY"),
        Relationship(source_entity_id=boost_policy.id, target_entity_id=new_jersey.id,  relation_type="APPLIES_IN"),
        Relationship(source_entity_id=oddsboost.id,    target_entity_id=nfl_mvp.id,     relation_type="SUPPORTS"),
    ]
    for r in rels:
        kg.upsert_relationship(r)

    # ── Cross-links: entity ↔ chunk ──────────────────────────────────────────
    mahomes.source_chunks.append(sports_chunk.id)
    sports_chunk.entity_refs.append(mahomes.id)

    chiefs.source_chunks.append(sports_chunk.id)
    sports_chunk.entity_refs.append(chiefs.id)
