import sqlite3
import json
from pathlib import Path

# The database lives in the config folder, scoped to the current board!
DB_DIR = Path.home() / ".config" / "tuido"

def get_db_path() -> Path:
    import config
    cfg = config.load_config() or {}
    board_alias = cfg.get("CURRENT_BOARD", "default")
    return DB_DIR / f"tuido_{board_alias}.db"

def get_connection():
    """Establishes a connection to the local SQLite database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    # This row_factory lets us access SQL columns by name like a Python dictionary
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the tasks table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Schema: id, title, status, tags, description, sync_status, due_date, priority, assignee, board_id
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
            board_id TEXT
        )
    ''')
    
    # Migration: Add board_id if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN board_id TEXT")
    except: pass
    
    conn.commit()
    conn.close()

def get_current_board_id():
    import config
    cfg = config.load_config()
    return cfg.get("NOTION_DATABASE_ID", "default")

# --- CLOUD FETCHING ---

def save_tasks_from_cloud(tasks_list: list) -> None:
    """Wipes the local cache for the CURRENT board and saves a fresh batch."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Only delete synced tasks for THIS board!
    cursor.execute("DELETE FROM tasks WHERE sync_status = 'synced' AND board_id = ?", (board_id,))
    
    for task in tasks_list:
        cursor.execute("SELECT sync_status FROM tasks WHERE id = ?", (task["id"],))
        row = cursor.fetchone()
        
        # If the task isn't in our local DB, or it's fully synced, update it from the cloud.
        # If it's pending an offline update/delete, leave our local offline version alone!
        if not row or row["sync_status"] == 'synced':
            tags_json = json.dumps(task.get("tags", []))
            cursor.execute('''
                INSERT OR REPLACE INTO tasks (id, title, status, tags, description, sync_status, due_date, priority, assignee, board_id)
                VALUES (?, ?, ?, ?, ?, 'synced', ?, ?, ?, ?)
            ''', (task["id"], task["name"], task["status"], tags_json, task.get("desc"), task.get("due_date"), task.get("priority"), task.get("assignee"), board_id))
            
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
            "assignee": row["assignee"]
        })
        
    conn.close()
    return formatted_tasks

# --- THE OFFLINE QUEUE ENGINE ---

def queue_create(temp_id: str, title: str, status: str, tags: list, description: str, due_date: str = None, priority: str = None, assignee: str = None):
    """Saves a new task offline until it can be pushed to Notion."""
    board_id = get_current_board_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (id, title, status, tags, description, sync_status, due_date, priority, assignee, board_id)
        VALUES (?, ?, ?, ?, ?, 'pending_create', ?, ?, ?, ?)
    ''', (temp_id, title, status, json.dumps(tags), description, due_date, priority, assignee, board_id))
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