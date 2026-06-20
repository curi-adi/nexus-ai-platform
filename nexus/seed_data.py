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
            content="LeBron James is a forward for the Los Angeles Lakers in the NBA. "
                    "He is a four-time NBA champion, four-time NBA MVP, and the all-time "
                    "leading scorer in NBA history. James is one of the most marketable "
                    "athletes in professional sports.",
            domain=DataDomain.SPORTS,
            sensitivity=SensitivityLevel.PUBLIC,
            metadata={},
        ),
        dict(
            content="California (CA) requires NBA teams and their analytics partners to comply "
                    "with CCPA when processing player performance data. Any biometric or "
                    "health-related player data collected during training or games must have "
                    "explicit written consent per the NBA Collective Bargaining Agreement (CBA).",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={"jurisdiction": "CA"},
        ),
        dict(
            content="New York (NY) teams must obtain explicit consent from the NBA Players "
                    "Association before sharing player biometric data with third-party analytics "
                    "platforms. All data-sharing agreements must be filed with the state "
                    "attorney general's office annually.",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={"jurisdiction": "NY"},
        ),
        dict(
            content="The PlayerIQ feature supports per-game performance analytics, shot-chart "
                    "visualization, and lineup optimization recommendations. Metrics are updated "
                    "within two hours of game completion and are subject to team-specific data "
                    "sharing agreements under the NBA CBA.",
            domain=DataDomain.PRODUCT,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={},
        ),
        dict(
            content="The NBA Collective Bargaining Agreement (CBA) mandates that player salary "
                    "cap data and contract information shared with third-party platforms must be "
                    "anonymized unless the player has signed an individual data authorization. "
                    "Violations may result in league fines and loss of analytics access.",
            domain=DataDomain.COMPLIANCE,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata={},
        ),
        dict(
            content="INTERNAL — Incident postmortem: stats sync failure on 2026-04-10. "
                    "Affected platform: Lakers analytics dashboard showed stale box-score data "
                    "for 6 hours. Root cause: race condition in the stats ingestion worker. "
                    "Resolved in hotfix v2.3.1.",
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
    lebron = Entity(
        name="LeBron James",
        canonical_name="LeBron James",
        entity_type=EntityType.PLAYER,
        aliases=["LeBron", "King James"],
        domain=DataDomain.SPORTS,
        properties={"position": "SF", "status": "active"},
        embedding=embedder.encode("LeBron James"),
    )
    lakers = Entity(
        name="Los Angeles Lakers",
        canonical_name="Los Angeles Lakers",
        entity_type=EntityType.TEAM,
        aliases=["Lakers", "LA Lakers"],
        domain=DataDomain.SPORTS,
        properties={"city": "Los Angeles"},
        embedding=embedder.encode("Los Angeles Lakers"),
    )
    nba = Entity(
        name="NBA",
        canonical_name="NBA",
        entity_type=EntityType.LEAGUE,
        aliases=["National Basketball Association"],
        domain=DataDomain.SPORTS,
        properties={"sport": "Basketball"},
        embedding=embedder.encode("NBA"),
    )
    nba_mvp = Entity(
        name="NBA MVP",
        canonical_name="NBA MVP",
        entity_type=EntityType.MARKET,
        aliases=["Most Valuable Player"],
        domain=DataDomain.SPORTS,
        properties={"type": "award"},
        embedding=embedder.encode("NBA MVP"),
    )
    cba_policy = Entity(
        name="CBA Data Policy",
        canonical_name="CBA Data Policy",
        entity_type=EntityType.POLICY,
        aliases=["Collective Bargaining Agreement", "CBA"],
        properties={"version": "2023"},
        embedding=embedder.encode("CBA Data Policy"),
    )
    california = Entity(
        name="California",
        canonical_name="California",
        entity_type=EntityType.JURISDICTION,
        aliases=["CA"],
        properties={"compliance": "CCPA"},
        embedding=embedder.encode("California"),
    )
    playeriq = Entity(
        name="PlayerIQ",
        canonical_name="PlayerIQ",
        entity_type=EntityType.PRODUCT,
        aliases=["Player IQ"],
        properties={"version": "2.1"},
        embedding=embedder.encode("PlayerIQ"),
    )

    for e in [lebron, lakers, nba, nba_mvp, cba_policy, california, playeriq]:
        kg.upsert_entity(e)

    # ── Relationships ─────────────────────────────────────────────────────────
    rels = [
        Relationship(source_entity_id=lebron.id,      target_entity_id=lakers.id,     relation_type="PLAYS_FOR"),
        Relationship(source_entity_id=lakers.id,      target_entity_id=nba.id,         relation_type="COMPETES_IN"),
        Relationship(source_entity_id=nba_mvp.id,     target_entity_id=cba_policy.id,  relation_type="GOVERNED_BY"),
        Relationship(source_entity_id=cba_policy.id,  target_entity_id=california.id,  relation_type="APPLIES_IN"),
        Relationship(source_entity_id=playeriq.id,    target_entity_id=nba_mvp.id,     relation_type="TRACKS"),
    ]
    for r in rels:
        kg.upsert_relationship(r)

    # ── Cross-links: entity ↔ chunk ──────────────────────────────────────────
    lebron.source_chunks.append(sports_chunk.id)
    sports_chunk.entity_refs.append(lebron.id)

    lakers.source_chunks.append(sports_chunk.id)
    sports_chunk.entity_refs.append(lakers.id)
