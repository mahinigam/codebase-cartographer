"""Exceptions shared across the indexing and persistence layers."""


class RepositoryTooLarge(ValueError):
    """Raised when an operation would violate a configured size cap."""
