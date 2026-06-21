"""Unit tests for db.py — all operations run against a temp SQLite file."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import datetime


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "get_current_board_id", lambda: "test_board")
    db.init_db()
    yield
    # Clean up connections
    try:
        conn = db.get_connection()
        conn.close()
    except Exception:
        pass


# ── schema ────────────────────────────────────────────────────────────────────

def test_init_creates_tasks_table():
    import db
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    assert cursor.fetchone() is not None
    conn.close()


# ── create ────────────────────────────────────────────────────────────────────

def test_queue_create_appears_in_not_started():
    import db
    db.queue_create("t1", "My Task", "Not started", ["a", "b"], "desc", None, "High", None)
    tasks = db.get_all_local_tasks()
    names = [t["name"] for t in tasks.get("Not started", [])]
    assert "My Task" in names


def test_queue_create_tags_roundtrip():
    import db
    db.queue_create("t2", "Tagged", "Not started", ["x", "y"], "", None, None, None)
    tasks = db.get_all_local_tasks()
    card = next(t for t in tasks["Not started"] if t["id"] == "t2")
    assert card["tags"] == ["x", "y"]


def test_queue_create_sets_pending_create_status():
    import db
    db.queue_create("t3", "Pending", "Not started", [], "", None, None, None)
    pending = db.get_pending_tasks()
    assert any(p["id"] == "t3" for p in pending)


# ── update ────────────────────────────────────────────────────────────────────

def test_queue_update_changes_title_and_column():
    import db
    db.queue_create("u1", "Original", "Not started", [], "", None, None, None)
    db.mark_synced("u1")  # mark synced so update sets pending_update
    db.queue_update("u1", "Updated", "In progress", "new desc")
    tasks = db.get_all_local_tasks()
    in_prog = [t for t in tasks.get("In progress", []) if t["id"] == "u1"]
    assert len(in_prog) == 1
    assert in_prog[0]["name"] == "Updated"


def test_queue_update_preserves_pending_create_for_offline_task():
    import db
    db.queue_create("local_offline", "New", "Not started", [], "", None, None, None)
    db.queue_update("local_offline", "New Updated", "In progress", "")
    pending = db.get_pending_tasks()
    task = next((p for p in pending if p["id"] == "local_offline"), None)
    assert task is not None
    assert task["sync_status"] == "pending_create"


# ── delete ────────────────────────────────────────────────────────────────────

def test_queue_delete_local_task_removes_row():
    import db
    db.queue_create("local_del", "Bye", "Not started", [], "", None, None, None)
    db.queue_delete("local_del")
    tasks = db.get_all_local_tasks()
    assert not any(t["id"] == "local_del" for t in tasks.get("Not started", []))


def test_queue_delete_synced_task_marks_pending_delete():
    import db
    db.queue_create("synced_del", "Remote Task", "Not started", [], "", None, None, None)
    db.mark_synced("synced_del")
    db.queue_delete("synced_del")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sync_status FROM tasks WHERE id = ?", ("synced_del",))
    row = cursor.fetchone()
    conn.close()
    assert row["sync_status"] == "pending_delete"


# ── stats ─────────────────────────────────────────────────────────────────────

def test_stats_total_count():
    import db
    db.queue_create("s1", "A", "Not started", [], "", None, None, None)
    db.queue_create("s2", "B", "In progress", [], "", None, None, None)
    assert db.get_stats()["total"] == 2


def test_stats_done_count():
    import db
    db.queue_create("d1", "Done Task", "Done", [], "", None, None, None)
    db.queue_create("d2", "Todo", "Not started", [], "", None, None, None)
    stats = db.get_stats()
    assert stats["done"] == 1


def test_stats_overdue_excludes_done():
    import db
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    db.queue_create("o1", "Overdue Todo", "Not started", [], "", yesterday, None, None)
    db.queue_create("o2", "Overdue Done", "Done", [], "", yesterday, None, None)
    stats = db.get_stats()
    assert stats["overdue"] == 1  # only the Not started one counts


def test_stats_pending_sync():
    import db
    db.queue_create("p1", "Pending", "Not started", [], "", None, None, None)
    db.queue_create("p2", "Also Pending", "Not started", [], "", None, None, None)
    assert db.get_stats()["pending_sync"] == 2


# ── mark_synced ───────────────────────────────────────────────────────────────

def test_mark_synced_clears_pending():
    import db
    db.queue_create("ms1", "Task", "Not started", [], "", None, None, None)
    db.mark_synced("ms1")
    pending = db.get_pending_tasks()
    assert not any(p["id"] == "ms1" for p in pending)


def test_mark_synced_with_id_swap():
    import db
    db.queue_create("local_abc", "Task", "Not started", [], "", None, None, None)
    db.mark_synced("local_abc", "notion_real_id_xyz")
    tasks = db.get_all_local_tasks()
    all_ids = [t["id"] for tasks_list in tasks.values() for t in tasks_list]
    assert "notion_real_id_xyz" in all_ids
    assert "local_abc" not in all_ids


# ── unique statuses ───────────────────────────────────────────────────────────

def test_get_unique_statuses():
    import db
    db.queue_create("u1", "T1", "Not started", [], "", None, None, None)
    db.queue_create("u2", "T2", "In progress", [], "", None, None, None)
    db.queue_create("u3", "T3", "In progress", [], "", None, None, None)
    statuses = db.get_unique_statuses()
    assert set(statuses) == {"Not started", "In progress"}


# ── hard_delete ───────────────────────────────────────────────────────────────

def test_hard_delete_removes_row():
    import db
    db.queue_create("hd1", "To Delete", "Not started", [], "", None, None, None)
    db.mark_synced("hd1")
    db.hard_delete("hd1")
    tasks = db.get_all_local_tasks()
    all_ids = [t["id"] for lst in tasks.values() for t in lst]
    assert "hd1" not in all_ids


def test_hard_delete_nonexistent_is_safe():
    import db
    db.hard_delete("does_not_exist")  # should not raise


# ── update_recurring_interval ─────────────────────────────────────────────────

def test_update_recurring_interval_sets_value():
    import db
    db.queue_create("ri1", "Weekly", "Not started", [], "", None, None, None)
    db.update_recurring_interval("ri1", "weekly")
    tasks = db.get_all_local_tasks()
    card = next(t for t in tasks["Not started"] if t["id"] == "ri1")
    assert card["recurring_interval"] == "weekly"


def test_update_recurring_interval_clears_value():
    import db
    db.queue_create("ri2", "Was Weekly", "Not started", [], "", None, None, None, "weekly")
    db.update_recurring_interval("ri2", None)
    tasks = db.get_all_local_tasks()
    card = next(t for t in tasks["Not started"] if t["id"] == "ri2")
    assert card["recurring_interval"] is None


# ── save_tasks_from_cloud preserves recurring fields ─────────────────────────

def test_save_tasks_from_cloud_preserves_recurring_interval():
    import db
    # Simulate a task that was synced and has a local recurring_interval
    db.queue_create("cloud1", "Standup", "Not started", [], "", None, None, None, "weekly")
    db.mark_synced("cloud1")

    # Now a cloud pull arrives — it knows nothing about recurring_interval
    cloud_tasks = [{"id": "cloud1", "name": "Standup", "status": "Not started",
                    "tags": [], "desc": "", "due_date": None, "priority": None, "assignee": None}]
    db.save_tasks_from_cloud(cloud_tasks)

    tasks = db.get_all_local_tasks()
    card = next(t for t in tasks["Not started"] if t["id"] == "cloud1")
    assert card["recurring_interval"] == "weekly"  # must survive the cloud pull
