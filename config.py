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
    """Return dict of alias → database_url for saved boards."""
    return load_config().get("boards", {})


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


def save_board(alias: str, url: str) -> None:
    """Save a board alias → url mapping."""
    cfg = load_config()
    boards = cfg.get("boards", {})
    boards[alias] = url
    cfg["boards"] = boards
    save_config(cfg)


def is_configured() -> bool:
    """Return True if both token and database URL are set."""
    return bool(get_token() and get_database_url())


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
