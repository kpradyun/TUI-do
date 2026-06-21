"""
config.py — Configuration management for TUI-do.

Stores and retrieves Notion credentials from a platform-appropriate
location (~/.config/tuido/config.json).  Credentials are NEVER written
to the project directory or committed to git.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

APP_NAME = "tuido"

# ── config path ───────────────────────────────────────────────────────────────

def _config_dir() -> Path:
    """Return the OS-appropriate config directory, creating it if needed."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path() -> Path:
    return _config_dir() / "config.json"


# ── load / save ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load the config file. Returns {} if file does not exist."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict) -> None:
    """Persist the config dict to disk with restricted permissions (owner-only)."""
    path = _config_path()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    # Restrict file to owner read/write only (unix)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows doesn't support chmod the same way — acceptable


# ── accessors ─────────────────────────────────────────────────────────────────

def get_token() -> Optional[str]:
    """Return the stored Notion integration token, or None."""
    return load_config().get("notion_token") or None


def get_database_url() -> Optional[str]:
    """Return the last-used Notion database URL, or None."""
    return load_config().get("database_url") or None


def get_all_boards() -> dict[str, str]:
    """Return dict of alias → database_id for saved boards."""
    return load_config().get("boards", {})


def get_current_board() -> str:
    """Return the currently active board alias."""
    return load_config().get("current_board", "default")


def set_current_board(alias: str) -> None:
    """Persist the currently active board alias."""
    cfg = load_config()
    cfg["current_board"] = alias
    save_config(cfg)


def switch_board(target: str) -> bool:
    """Switch to a saved board by alias. Returns True if the alias exists."""
    cfg = load_config()
    boards = cfg.get("boards", {})
    if target not in boards:
        return False
    cfg["current_board"] = target
    save_config(cfg)
    return True


def get_current_db_id() -> Optional[str]:
    """Return the Notion database ID for the currently active board."""
    cfg = load_config()
    current = cfg.get("current_board", "default")
    boards = cfg.get("boards", {})
    return boards.get(current) or cfg.get("notion_database_id")


def set_token(token: str) -> None:
    """Persist the Notion integration token."""
    if not token.startswith("secret_") and not token.startswith("ntn_"):
        raise ValueError(
            "Invalid Notion token format. Tokens typically start with 'secret_' or 'ntn_'."
        )
    cfg = load_config()
    cfg["notion_token"] = token
    save_config(cfg)


def set_database_url(url: str) -> None:
    """Persist the active Notion database URL."""
    url = url.strip()
    if not url.startswith("https://www.notion.so/") and not _looks_like_db_id(url):
        raise ValueError(
            "Expected a Notion database URL (https://www.notion.so/...) "
            "or a 32-character database ID."
        )
    cfg = load_config()
    cfg["database_url"] = url
    save_config(cfg)


def save_board(alias: str, db_id: str) -> None:
    """Save a board alias → database_id mapping."""
    cfg = load_config()
    boards = cfg.get("boards", {})
    boards[alias] = db_id
    cfg["boards"] = boards
    save_config(cfg)


def is_configured() -> bool:
    """Return True if both token and database URL are set."""
    return bool(get_token() and get_database_url())


def is_local_only() -> bool:
    """Return True if running without Notion (local SQLite only)."""
    return bool(load_config().get("local_only"))


def set_local_only() -> None:
    """Configure the app to run without Notion (local-only mode)."""
    cfg = load_config()
    cfg["local_only"] = True
    cfg["backend"] = "local"
    cfg.setdefault("current_board", "local")
    cfg.setdefault("boards", {})["local"] = "local"
    save_config(cfg)


# ── WIP limits ────────────────────────────────────────────────────────────────

def get_wip_limits() -> dict[str, int]:
    """Return WIP limit dict: {status: max_task_count}."""
    return load_config().get("wip_limits", {})


def set_wip_limit(status: str, limit: int) -> None:
    """Set the WIP limit for a column. limit=0 removes the limit."""
    cfg = load_config()
    if limit <= 0:
        cfg.setdefault("wip_limits", {}).pop(status, None)
    else:
        cfg.setdefault("wip_limits", {})[status] = limit
    save_config(cfg)


def clear_wip_limit(status: str) -> None:
    """Remove the WIP limit for a column."""
    cfg = load_config()
    cfg.setdefault("wip_limits", {}).pop(status, None)
    save_config(cfg)


# ── Sync backend ──────────────────────────────────────────────────────────────

def get_backend_type() -> str:
    """Return active backend: 'notion' | 'json' | 'local'."""
    if is_local_only():
        return "local"
    return load_config().get("backend", "notion")


def set_backend_type(backend: str) -> None:
    """Persist the sync backend choice."""
    cfg = load_config()
    cfg["backend"] = backend
    if backend == "local":
        cfg["local_only"] = True
    else:
        cfg.pop("local_only", None)
    save_config(cfg)


def get_json_sync_path() -> str:
    """Return the JSON sync file path (used by the JSON backend)."""
    default = str(Path.home() / "tuido_sync.json")
    return load_config().get("json_sync_path", default)


def set_json_sync_path(path: str) -> None:
    cfg = load_config()
    cfg["json_sync_path"] = path
    save_config(cfg)


def clear_config() -> None:
    """Remove all stored configuration (for testing or reset)."""
    path = _config_path()
    if path.exists():
        path.unlink()


# ── helpers ───────────────────────────────────────────────────────────────────

def _looks_like_db_id(s: str) -> bool:
    """Check if string looks like a raw 32-hex-char Notion DB ID."""
    clean = s.replace("-", "")
    return len(clean) == 32 and all(c in "0123456789abcdefABCDEF" for c in clean)


def extract_database_id(url_or_id: str) -> str:
    """
    Extract the Notion database ID from a full URL or return the raw ID.

    Examples:
        "https://www.notion.so/MyWorkspace/abc123...?v=..." → "abc123..."
        "abc123def456..."  → "abc123def456..."
    """
    url_or_id = url_or_id.strip()
    if url_or_id.startswith("https://"):
        # The ID is the last path segment before any query string
        path = url_or_id.split("?")[0].rstrip("/")
        segment = path.split("/")[-1]
        # Strip workspace prefix if present (e.g. "WorkspaceName-<id>")
        if "-" in segment:
            segment = segment.split("-")[-1]
        return segment
    return url_or_id
