class AccessError(Exception):
    """Raised when a principal lacks permission for the requested operation."""


class ResolutionError(Exception):
    """Raised when an entity cannot be resolved and the caller requires one."""
