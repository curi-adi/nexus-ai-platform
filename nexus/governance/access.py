from nexus.core.models import AccessClaim, KnowledgeChunk

_LEVEL = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
GOVERNED_ATTRS = {"jurisdiction"}        # only these metadata keys gate access


def permits(claim: AccessClaim, chunk: KnowledgeChunk) -> bool:
    """Fail-closed ABAC. Returns True only if every check passes."""
    if _LEVEL[chunk.sensitivity.value] > _LEVEL[claim.max_sensitivity.value]:
        return False
    if chunk.domain not in claim.domains:
        return False
    if claim.collections and chunk.collection not in claim.collections:
        return False
    for attr in GOVERNED_ATTRS:
        required = chunk.metadata.get(attr)
        allowed = claim.attributes.get(attr)
        if required is not None and allowed != "*" and allowed != required:
            return False
    return True
