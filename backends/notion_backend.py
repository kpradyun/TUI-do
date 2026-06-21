"""Notion sync backend — thin wrapper over the existing api module."""
from __future__ import annotations

from backends.base import SyncBackend
import api


class NotionBackend(SyncBackend):
    """Syncs tasks with a Notion database."""

    @property
    def name(self) -> str:
        return "notion"

    def is_available(self) -> bool:
        notion, db_id = api.get_client()
        return notion is not None and db_id is not None

    def full_sync(self) -> bool:
        return api.full_sync()

    def get_schema_statuses(self) -> list[str]:
        return api.get_status_options()

    def clear_cache(self) -> None:
        api.clear_cache()
