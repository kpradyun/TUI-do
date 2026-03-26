import json
import httpx
from notion_client import Client
import config
import db

def get_client():
    """Helper to quickly grab the Notion client and database ID."""
    cfg = config.load_config()
    if not cfg:
        return None, None
        
    current_alias = cfg.get("CURRENT_BOARD", "default")
    db_id = cfg.get("BOARDS", {}).get(current_alias) or cfg.get("NOTION_DATABASE_ID")
    
    return Client(auth=cfg["NOTION_TOKEN"]), db_id

def get_comments(page_id: str) -> list:
    """Fetches comments for a specific page/task."""
    notion, _ = get_client()
    if not notion: return []
    try:
        res = notion.comments.list(block_id=page_id)
        # Format: [{"text": "Hello", "author": "Name", "time": "2023-..."}]
        comments = []
        for c in res.get("results", []):
            text = "".join(t.get("text", {}).get("content", "") for t in c.get("rich_text", []))
            author = c.get("created_by", {}).get("name") or "Unknown"
            comments.append({"text": text, "author": author})
        return comments
    except Exception:
        return []

def get_subtasks(page_id: str) -> list:
    """Fetches 'to_do' block children for a specific page."""
    notion, _ = get_client()
    if not notion: return []
    try:
        res = notion.blocks.children.list(block_id=page_id)
        todos = []
        for b in res.get("results", []):
            if b.get("type") == "to_do":
                text = "".join(t.get("text", {}).get("content", "") for t in b["to_do"].get("rich_text", []))
                checked = b["to_do"].get("checked", False)
                todos.append({"text": text, "checked": checked})
        return todos
    except Exception:
        return []

_user_cache: dict = {}  # {"Pradyun K": "notion-user-uuid"}

def get_workspace_users() -> dict:
    """Fetches all workspace members and returns a name->user_id mapping."""
    global _user_cache
    if _user_cache:
        return _user_cache
    notion, _ = get_client()
    if not notion: return {}
    try:
        res = notion.users.list()
        for u in res.get("results", []):
            name = u.get("name")
            uid = u.get("id")
            if name and uid:
                _user_cache[name.lower()] = uid
                _user_cache[name] = uid  # also store exact casing
        return _user_cache
    except Exception:
        return {}

_schema_cache: dict = {}

def get_db_schema() -> dict:
    """Retrieves the database schema to find the correct property names."""
    global _schema_cache
    if _schema_cache:
        return _schema_cache
    notion, db_id = get_client()
    if not notion: return {}
    try:
        res = notion.databases.retrieve(database_id=db_id)
        props = res.get("properties", {})
        # Map: {"people": ["Assign", "Assignee"], "select": ["Priority", "Level"], "date": ["Due Date"]}
        _schema_cache = {}
        for name, data in props.items():
            ptype = data.get("type")
            if ptype not in _schema_cache:
                _schema_cache[ptype] = []
            _schema_cache[ptype].append(name)
        return _schema_cache
    except Exception:
        return {}

def clear_cache():
    """Wipes the schema and user cache. Call this when switching boards."""
    global _schema_cache, _user_cache
    _schema_cache = {}
    _user_cache = {}

def pull_from_cloud() -> bool:
    """Fetches all tasks from Notion and saves them to the local SQLite DB."""
    notion, db_id = get_client()
    if not notion: return False
    
    try:
        flat_tasks = []
        has_more = True
        next_cursor = None
        
        while has_more:
            # Fetch data from Notion using httpx directly since the SDK is missing the method
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            headers = {
                "Authorization": f"Bearer {notion.options.auth}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            body = {}
            if next_cursor:
                body["start_cursor"] = next_cursor
                
            res = httpx.post(url, headers=headers, json=body)
            res.raise_for_status()
            response = res.json()
            
            for page in response.get("results", []):
                props = page.get("properties", {})
                page_id = page.get("id")
                
                # Title
                title_prop = props.get("Name", {}).get("title", [])
                task_name = title_prop[0].get("text", {}).get("content") if title_prop else "Untitled"
                
                # Status
                status_prop = props.get("Status", {}).get("status", {})
                task_status = status_prop.get("name") if status_prop else "Not started"
                
                # Description
                desc_prop = props.get("Description", {}).get("rich_text", [])
                task_desc = "".join([t.get("text", {}).get("content", "") for t in desc_prop])
                
                # Tags
                tags_list = [tag.get("name") for tag in props.get("Tags", {}).get("multi_select", []) if tag.get("name")]
                
                # Due Date
                due_date = None
                date_prop = props.get("Due Date", {}).get("date")
                if date_prop:
                    due_date = date_prop.get("start")
                    
                # Flexible Property Lookups
                def find_prop(names: list, type: str):
                    # 1. Try specified common names first
                    for name in names:
                        prop = props.get(name)
                        if prop and prop.get("type") == type:
                            return prop
                    # 2. Fallback: just find the FIRST property of this type in the entire page!
                    for name, prop in props.items():
                        if prop and prop.get("type") == type:
                            return prop
                    return None

                # 1. Due Date
                due_date = None
                due_prop = find_prop(["Due Date", "Due", "Deadline", "Date"], "date")
                if due_prop:
                    due_date = (due_prop.get("date") or {}).get("start")
                    
                # 2. Priority
                priority = None
                prio_prop = find_prop(["Priority", "Level", "Urgency"], "select")
                if prio_prop:
                    priority_data = prio_prop.get("select")
                    if priority_data:
                        priority = priority_data.get("name")
                        
                # 3. Assignee
                assignee = None
                assign_prop_data = find_prop(["Assign", "Assignee", "Assigned to", "Owner"], "people")
                if assign_prop_data:
                    people = assign_prop_data.get("people", [])
                    if people:
                        person = people[0]
                        assignee = person.get("name") or person.get("person", {}).get("email") or "Unknown"
                
                flat_tasks.append({
                    "id": page_id, 
                    "name": task_name, 
                    "status": task_status, 
                    "tags": tags_list, 
                    "desc": task_desc,
                    "due_date": due_date,
                    "priority": priority,
                    "assignee": assignee
                })
                
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")
        
        # Hand the fresh data to our smart DB engine
        db.save_tasks_from_cloud(flat_tasks)
        return True
    except Exception as e:
        return False

def push_offline_queue() -> bool:
    """
    The magic function! Looks for any tasks we created, updated, or deleted
    while offline, and pushes those exact changes up to Notion.
    """
    notion, db_id = get_client()
    if not notion: return False
    
    # Grab everything waiting in the SQLite queue
    pending_tasks = db.get_pending_tasks()
    success = True
    
    for task in pending_tasks:
        try:
            status = task["sync_status"]
            task_id = task["id"]
            
            # --- 1. HANDLE PENDING CREATES ---
            if status == "pending_create":
                tags = json.loads(task["tags"]) if task["tags"] else []
                props = {
                    "Name": {"title": [{"text": {"content": task["title"]}}]},
                    "Status": {"status": {"name": task["status"]}},
                    "Tags": {"multi_select": [{"name": t} for t in tags]}
                }
                
                schema = get_db_schema()
                
                if task["description"]:
                    props["Description"] = {"rich_text": [{"text": {"content": task["description"]}}]}
                
                # Dynamic mapping for Due Date
                due_name = next((n for n in schema.get("date", []) if n in ["Due Date", "Due", "Deadline", "Date"]), "Due Date")
                if task["due_date"]:
                    props[due_name] = {"date": {"start": task["due_date"]}}
                
                # Dynamic mapping for Priority
                prio_name = next((n for n in schema.get("select", []) if n in ["Priority", "Level", "Urgency"]), "Priority")
                if task["priority"]:
                    props[prio_name] = {"select": {"name": task["priority"]}}
                
                # Dynamic mapping for Assignee
                assign_name = next((n for n in schema.get("people", []) if n in ["Assign", "Assignee", "Assigned to", "Owner"]), "Assign")
                if task["assignee"]:
                    users = get_workspace_users()
                    uid = users.get(task["assignee"]) or users.get(task["assignee"].lower())
                    if uid:
                        props[assign_name] = {"people": [{"object": "user", "id": uid}]}
                
                response = notion.pages.create(parent={"database_id": db_id}, properties=props)
                db.mark_synced(old_id=task_id, new_real_id=response["id"])

            elif status == "pending_update":
                props = {
                    "Name": {"title": [{"text": {"content": task["title"]}}]},
                    "Status": {"status": {"name": task["status"]}}
                }
                schema = get_db_schema()
                
                if task["description"]:
                    props["Description"] = {"rich_text": [{"text": {"content": task["description"]}}]}
                
                due_name = next((n for n in schema.get("date", []) if n in ["Due Date", "Due", "Deadline", "Date"]), "Due Date")
                if task["due_date"]:
                    props[due_name] = {"date": {"start": task["due_date"]}}
                
                prio_name = next((n for n in schema.get("select", []) if n in ["Priority", "Level", "Urgency"]), "Priority")
                if task["priority"]:
                    props[prio_name] = {"select": {"name": task["priority"]}}
                
                assign_name = next((n for n in schema.get("people", []) if n in ["Assign", "Assignee", "Assigned to", "Owner"]), "Assign")
                if task["assignee"]:
                    users = get_workspace_users()
                    uid = users.get(task["assignee"]) or users.get(task["assignee"].lower())
                    if uid:
                        props[assign_name] = {"people": [{"object": "user", "id": uid}]}
                
                notion.pages.update(page_id=task_id, properties=props)
                db.mark_synced(task_id)

            # --- 3. HANDLE PENDING DELETES ---
            elif status == "pending_delete":
                notion.pages.update(page_id=task_id, archived=True)
                
                # Once it's deleted in the cloud, permanently erase it from our local SQLite cache
                conn = db.get_connection()
                conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
                
        except Exception as e:
            # If a single task fails to sync, we catch the error, leave it in the queue, 
            # and try again on the next loop.
            success = False
            
    return success

def full_sync() -> bool:
    """The ultimate command: Pushes offline edits first, then pulls fresh data."""
    push_success = push_offline_queue()
    pull_success = pull_from_cloud()
    return push_success and pull_success