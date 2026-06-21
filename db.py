import sqlite3
import json
from pathlib import Path

# The database lives in the config folder, scoped to the current board!
DB_DIR = Path.home() / ".config" / "tuido"

def get_db_path() -> Path:
    import config
    board_alias = config.get_current_board()
    return DB_DIR / f"tuido_{board_alias}.db"

def get_connection():
    """Establishes a connection to the local SQLite database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    # This row_factory lets us access SQL columns by name like a Python dictionary
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the tasks table and runs any pending column migrations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            tags TEXT,
            description TEXT,
            sync_status TEXT,
            due_date TEXT,
            priority TEXT,
            assignee TEXT,
            board_id TEXT,
            recurring_interval TEXT,
            recurring_next_due TEXT
        )
    ''')

    # Non-destructive migrations — add columns that may be missing in older DBs
    _add_column_if_missing(cursor, "board_id", "TEXT")
    _add_column_if_missing(cursor, "recurring_interval", "TEXT")
    _add_column_if_missing(cursor, "recurring_next_due", "TEXT")

    conn.commit()
    conn.close()


def _add_column_if_missing(cursor, column: str, col_type: str) -> None:
    try:
        cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # column already exists

def get_current_board_id():
    import config
    return config.get_current_db_id() or "default"

# --- CLOUD FETCHING ---

def save_tasks_from_cloud(tasks_list: list) -> None:
    """Wipes the local cache for the CURRENT board and saves a fresh batch."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()

    # Snapshot local-only fields before deleting synced rows — cloud has no concept of these.
    cursor.execute(
        "SELECT id, recurring_interval, recurring_next_due FROM tasks WHERE sync_status = 'synced' AND board_id = ?",
        (board_id,),
    )
    local_meta = {
        row["id"]: (row["recurring_interval"], row["recurring_next_due"])
        for row in cursor.fetchall()
    }

    # Only delete synced tasks for THIS board!
    cursor.execute("DELETE FROM tasks WHERE sync_status = 'synced' AND board_id = ?", (board_id,))

    for task in tasks_list:
        cursor.execute("SELECT sync_status FROM tasks WHERE id = ?", (task["id"],))
        row = cursor.fetchone()

        # If the task isn't in our local DB, or it's fully synced, update it from the cloud.
        # If it's pending an offline update/delete, leave our local offline version alone!
        if not row or row["sync_status"] == 'synced':
            tags_json = json.dumps(task.get("tags", []))
            ri, rnd = local_meta.get(task["id"], (None, None))
            cursor.execute('''
                INSERT OR REPLACE INTO tasks
                    (id, title, status, tags, description, sync_status,
                     due_date, priority, assignee, board_id,
                     recurring_interval, recurring_next_due)
                VALUES (?, ?, ?, ?, ?, 'synced', ?, ?, ?, ?, ?, ?)
            ''', (
                task["id"], task["name"], task["status"], tags_json,
                task.get("desc"), task.get("due_date"), task.get("priority"),
                task.get("assignee"), board_id, ri, rnd,
            ))

    conn.commit()
    conn.close()


def hard_delete(task_id: str) -> None:
    """Permanently remove a task row (call after successful remote deletion)."""
    conn = get_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def update_recurring_interval(task_id: str, interval: str | None) -> None:
    """Update the recurring_interval for a task (local-only field, never pushed to cloud)."""
    conn = get_connection()
    conn.execute("UPDATE tasks SET recurring_interval = ? WHERE id = ?", (interval, task_id))
    conn.commit()
    conn.close()

def get_all_local_tasks() -> dict:
    """Retrieves tasks from SQLite for the current board."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Never show the user tasks that are marked for deletion
    cursor.execute("SELECT * FROM tasks WHERE sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)", (board_id,))
    rows = cursor.fetchall()
    
    formatted_tasks = {"Not started": [], "In progress": [], "Done": []}
    
    for row in rows:
        status = row["status"]
        if status not in formatted_tasks:
            formatted_tasks[status] = []
            
        formatted_tasks[status].append({
            "id": row["id"],
            "name": row["title"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "desc": row["description"],
            "sync_status": row["sync_status"],
            "due_date": row["due_date"],
            "priority": row["priority"],
            "assignee": row["assignee"],
            "recurring_interval": row["recurring_interval"],
        })
        
    conn.close()
    return formatted_tasks

# --- THE OFFLINE QUEUE ENGINE ---

def queue_create(temp_id: str, title: str, status: str, tags: list, description: str, due_date: str = None, priority: str = None, assignee: str = None, recurring_interval: str = None):
    """Saves a new task offline until it can be pushed to Notion."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (id, title, status, tags, description, sync_status, due_date, priority, assignee, board_id, recurring_interval)
        VALUES (?, ?, ?, ?, ?, 'pending_create', ?, ?, ?, ?, ?)
    ''', (temp_id, title, status, json.dumps(tags), description, due_date, priority, assignee, board_id, recurring_interval))
    conn.commit()
    conn.close()

def queue_update(task_id: str, title: str, status: str, description: str, due_date: str = None, priority: str = None, assignee: str = None, tags: list = None):
    """Updates a task offline."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # If the task was created offline and hasn't synced yet, keep it as 'pending_create'
    cursor.execute("SELECT sync_status, tags FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    
    new_status = 'pending_create' if (row and row["sync_status"] == 'pending_create') else 'pending_update'
    final_tags = json.dumps(tags) if tags is not None else (row["tags"] if row else None)
        
    cursor.execute('''
        UPDATE tasks SET title = ?, status = ?, description = ?, sync_status = ?, due_date = ?, priority = ?, assignee = ?, tags = ?
        WHERE id = ?
    ''', (title, status, description, new_status, due_date, priority, assignee, final_tags, task_id))
    conn.commit()
    conn.close()

def queue_delete(task_id: str):
    """Handles an offline delete request gracefully."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT sync_status FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    
    # If we created this task offline and never synced it, just completely delete it from the cache.
    if row and row["sync_status"] == 'pending_create':
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    else:
        # Otherwise, mark it so we can tell Notion to archive it later.
        cursor.execute("UPDATE tasks SET sync_status = 'pending_delete' WHERE id = ?", (task_id,))
        
    conn.commit()
    conn.close()

def get_pending_tasks():
    """Returns all tasks that are waiting in the offline queue for THE CURRENT BOARD."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE sync_status != 'synced' AND (board_id = ? OR board_id IS NULL)", (board_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_synced(old_id: str, new_real_id: str = None):
    """Marks a task as completely synced, swapping temporary IDs for real Notion IDs."""
    conn = get_connection()
    cursor = conn.cursor()

    if new_real_id and old_id != new_real_id:
        cursor.execute("UPDATE tasks SET id = ?, sync_status = 'synced' WHERE id = ?", (new_real_id, old_id))
    else:
        cursor.execute("UPDATE tasks SET sync_status = 'synced' WHERE id = ?", (old_id,))

    conn.commit()
    conn.close()


def get_stats() -> dict:
    """Return summary statistics for the current board."""
    import datetime
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)",
        (board_id,)
    )
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Done' AND sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)",
        (board_id,)
    )
    done_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND status != 'Done' AND sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)",
        (today, board_id)
    )
    overdue = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE sync_status NOT IN ('synced', 'pending_delete')"
    )
    pending_sync = cursor.fetchone()[0]

    conn.close()
    return {"total": total, "done": done_count, "overdue": overdue, "pending_sync": pending_sync}


def get_unique_statuses() -> list:
    """Return all unique status values present in the local DB for the current board."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT status FROM tasks WHERE sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)",
        (board_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row["status"] for row in rows if row["status"]]


def process_recurring_tasks() -> int:
    """
    Spawn new task instances for any recurring task that was completed and
    whose next-due date has arrived.  Returns the number of new tasks created.
    """
    import datetime
    import uuid as _uuid

    today = datetime.date.today()
    today_str = today.isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # Completed recurring tasks whose next spawn date is today or overdue
    cursor.execute("""
        SELECT * FROM tasks
        WHERE recurring_interval IS NOT NULL
          AND recurring_interval != ''
          AND status = 'Done'
          AND sync_status != 'pending_delete'
          AND (recurring_next_due IS NULL OR recurring_next_due <= ?)
    """, (today_str,))
    due_tasks = cursor.fetchall()

    created = 0
    for task in due_tasks:
        interval = task["recurring_interval"]

        if interval == "daily":
            next_due = today + datetime.timedelta(days=1)
        elif interval == "weekly":
            next_due = today + datetime.timedelta(weeks=1)
        elif interval == "monthly":
            m = today.month % 12 + 1
            y = today.year + (1 if today.month == 12 else 0)
            next_due = today.replace(year=y, month=m)
        else:
            continue

        next_due_str = next_due.isoformat()

        # Update the recurring_next_due on the completed original
        cursor.execute(
            "UPDATE tasks SET recurring_next_due = ? WHERE id = ?",
            (next_due_str, task["id"])
        )

        # Create the fresh instance
        new_id = f"local_{_uuid.uuid4().hex}"
        cursor.execute("""
            INSERT INTO tasks
                (id, title, status, tags, description, sync_status,
                 due_date, priority, assignee, board_id,
                 recurring_interval, recurring_next_due)
            VALUES (?, ?, 'Not started', ?, ?, 'pending_create',
                    ?, ?, ?, ?, ?, ?)
        """, (
            new_id, task["title"], task["tags"], task["description"],
            next_due_str, task["priority"], task["assignee"], task["board_id"],
            interval, next_due_str,
        ))
        created += 1

    conn.commit()
    conn.close()
    return created