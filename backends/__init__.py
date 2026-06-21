"""
Sync backend registry.

Usage:
    from backends import get_backend
    backend = get_backend()
    backend.full_sync()
"""
from __future__ import annotations

import config
from backends.base import SyncBackend


def get_backend() -> SyncBackend:
    """Return the active sync backend based on config."""
    backend_type = config.get_backend_type()
    if backend_type == "json":
        from backends.json_backend import JSONBackend
        return JSONBackend()
    if backend_type == "notion":
        from backends.notion_backend import NotionBackend
        return NotionBackend()
    # local-only: return a no-op backend
    from backends.base import NullBackend
    return NullBackend()
