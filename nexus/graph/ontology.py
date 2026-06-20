from nexus.core.models import EntityType

# Allowed relation types and the (source_type, target_type) they connect
RELATIONS: dict[str, tuple[EntityType, EntityType]] = {
    "PLAYS_FOR":      (EntityType.PLAYER,       EntityType.TEAM),
    "COMPETES_IN":    (EntityType.TEAM,         EntityType.LEAGUE),
    "PARTICIPATES_IN":(EntityType.PLAYER,       EntityType.EVENT),
    "PART_OF":        (EntityType.EVENT,        EntityType.LEAGUE),
    "HAS_MARKET":     (EntityType.EVENT,        EntityType.MARKET),
    "GOVERNED_BY":    (EntityType.MARKET,       EntityType.POLICY),
    "APPLIES_IN":     (EntityType.POLICY,       EntityType.JURISDICTION),
    "HAS_REGULATION": (EntityType.JURISDICTION, EntityType.REGULATION),
    "REGULATED_BY":   (EntityType.PRODUCT,      EntityType.REGULATION),
    "SUPPORTS":       (EntityType.PRODUCT,      EntityType.MARKET),
    "DESCRIBED_BY":   (EntityType.PLAYER,       EntityType.CHUNK),
}


def validate(rel_type: str, src_type: EntityType, tgt_type: EntityType) -> bool:
    """Returns True if the relationship is valid per the ontology."""
    expected = RELATIONS.get(rel_type)
    if expected is None:
        return False
    return expected == (src_type, tgt_type)
