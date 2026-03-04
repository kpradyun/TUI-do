import json
from notion_client import Client
import config
import db

def get_client():
    """Helper to quickly grab the Notion client and database ID."""
    cfg = config.load_config()
    if not cfg:
        return None, None
    return Client(auth=cfg["NOTION_TOKEN"]), cfg["NOTION_DATABASE_ID"]

def pull_from_cloud() -> bool:
    """Fetches all tasks from Notion and saves them to the local SQLite DB."""
    notion, db_id = get_client()
    if not notion: return False
    
    try:
        # Fetch data from Notion
        db_info = notion.databases.retrieve(database_id=db_id)
        response = notion.data_sources.query(data_source_id=db_info["data_sources"][0]["id"])
        
        flat_tasks = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            page_id = page.get("id")
            title_prop = props.get("Name", {}).get("title", [])
            task_name = title_prop[0].get("text", {}).get("content") if title_prop else "Untitled"
            status_prop = props.get("Status", {}).get("status", {})
            task_status = status_prop.get("name") if status_prop else "Not started"
            desc_prop = props.get("Description", {}).get("rich_text", [])
            task_desc = "".join([t.get("text", {}).get("content", "") for t in desc_prop])
            tags_list = [tag.get("name") for tag in props.get("Tags", {}).get("multi_select", []) if tag.get("name")]
            
            flat_tasks.append({
                "id": page_id, "name": task_name, "status": task_status, 
                "tags": tags_list, "desc": task_desc
            })
        
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
                if task["description"]:
                    props["Description"] = {"rich_text": [{"text": {"content": task["description"]}}]}
                
                # Push to Notion
                response = notion.pages.create(parent={"database_id": db_id}, properties=props)
                
                # Update SQLite: swap our fake temp_id with the real Notion ID!
                db.mark_synced(old_id=task_id, new_real_id=response["id"])

            # --- 2. HANDLE PENDING UPDATES ---
            elif status == "pending_update":
                props = {
                    "Name": {"title": [{"text": {"content": task["title"]}}]},
                    "Status": {"status": {"name": task["status"]}}
                }
                if task["description"]:
                    props["Description"] = {"rich_text": [{"text": {"content": task["description"]}}]}
                
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