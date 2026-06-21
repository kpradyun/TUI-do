"""Abstract base class for TUI-do sync backends."""
from __future__ import annotations

from abc import ABC, abstractmethod


class SyncBackend(ABC):
    """All sync backends implement this interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name shown in the UI."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend can be reached right now."""

    @abstractmethod
    def full_sync(self) -> bool:
        """Push pending local changes then pull remote state. Returns True on success."""

    def get_schema_statuses(self) -> list[str]:
        """Return custom status names defined by this backend (empty = use defaults)."""
        return []

    def clear_cache(self) -> None:
        """Invalidate any cached schema/user data."""


class NullBackend(SyncBackend):
    """No-op backend used in local-only mode."""

    @property
    def name(self) -> str:
        return "local"

    def is_available(self) -> bool:
        return True

    def full_sync(self) -> bool:
        return True
