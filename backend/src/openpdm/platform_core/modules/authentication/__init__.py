"""Public Authentication Platform Module contract."""

from typing import Protocol


class AuthenticationInterface(Protocol):
    """Authenticate users and manage application sessions."""
