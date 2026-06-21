"""Shared pytest fixtures that isolate file-system state for every test."""
from __future__ import annotations

import importlib
import sys
import pytest


@pytest.fixture(autouse=False)
def isolated_config(monkeypatch, tmp_path):
    """Redirect config reads/writes to a throw-away temp directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Force config module to recompute paths
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])
    yield tmp_path
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])


@pytest.fixture(autouse=False)
def isolated_db(monkeypatch, tmp_path):
    """Redirect SQLite to a throw-away temp directory and init a fresh schema."""
    import db as db_module
    monkeypatch.setattr(db_module, "DB_DIR", tmp_path)

    # Also patch get_current_board_id so it returns a stable value
    monkeypatch.setattr(db_module, "get_current_board_id", lambda: "test_board")

    db_module.init_db()
    yield tmp_path
