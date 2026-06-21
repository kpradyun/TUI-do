"""Unit tests for config.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import importlib


@pytest.fixture(autouse=True)
def fresh_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import config
    importlib.reload(config)
    yield
    importlib.reload(config)


def test_load_empty_config():
    import config
    assert config.load_config() == {}


def test_set_and_get_token():
    import config
    config.set_token("secret_abcdefghijklmnopqrstuvwxyz123456")
    assert config.get_token() == "secret_abcdefghijklmnopqrstuvwxyz123456"


def test_set_token_ntn_prefix():
    import config
    config.set_token("ntn_abc123def456ghi789jkl012mno345pqr")
    assert config.get_token().startswith("ntn_")


def test_invalid_token_raises():
    import config
    with pytest.raises(ValueError, match="Invalid Notion token"):
        config.set_token("not_a_real_token")


def test_save_and_retrieve_board():
    import config
    config.save_board("work", "abcdef1234567890abcdef1234567890")
    boards = config.get_all_boards()
    assert "work" in boards
    assert boards["work"] == "abcdef1234567890abcdef1234567890"


def test_switch_board():
    import config
    config.save_board("personal", "12345678901234567890123456789012")
    assert config.switch_board("personal")
    assert config.get_current_board() == "personal"


def test_switch_board_invalid():
    import config
    assert not config.switch_board("nonexistent_board")


def test_local_only_default_false():
    import config
    assert not config.is_local_only()


def test_set_local_only():
    import config
    config.set_local_only()
    assert config.is_local_only()
    assert config.get_backend_type() == "local"


def test_wip_limits_empty_by_default():
    import config
    assert config.get_wip_limits() == {}


def test_set_and_get_wip_limit():
    import config
    config.set_wip_limit("In progress", 3)
    assert config.get_wip_limits()["In progress"] == 3


def test_clear_wip_limit():
    import config
    config.set_wip_limit("In progress", 3)
    config.clear_wip_limit("In progress")
    assert "In progress" not in config.get_wip_limits()


def test_backend_type_default_notion():
    import config
    # Without local_only or explicit backend, defaults to notion
    config.set_token("secret_abcdefghijklmnopqrstuvwxyz123456")
    assert config.get_backend_type() == "notion"


def test_extract_database_id_from_url():
    import config
    url = "https://www.notion.so/MyWorkspace/abcdef1234567890abcdef1234567890?v=xyz"
    assert config.extract_database_id(url) == "abcdef1234567890abcdef1234567890"


def test_extract_database_id_raw():
    import config
    raw = "abcdef1234567890abcdef1234567890"
    assert config.extract_database_id(raw) == raw
