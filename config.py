import json
import re
from pathlib import Path

# Define the hidden config path: ~/.config/tuido/config.json
CONFIG_DIR = Path.home() / ".config" / "tuido"
CONFIG_FILE = CONFIG_DIR / "config.json"

def extract_notion_id(url_or_id: str) -> str:
    """Extracts the 32-character ID from a Notion URL, or returns it if already an ID."""
    # Removes hyphens and looks for 32 consecutive hex characters
    clean_string = url_or_id.replace('-', '')
    match = re.search(r'([a-f0-9]{32})', clean_string)
    if match:
        return match.group(1)
    return url_or_id # Fallback

def load_config() -> dict | None:
    """Loads the config file if it exists."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                
            # --- UPGRADE OLD CONFIGS ---
            dirty = False
            if "BOARDS" not in data:
                db_id = data.get("NOTION_DATABASE_ID")
                data["BOARDS"] = {"default": db_id} if db_id else {}
                dirty = True
            if "CURRENT_BOARD" not in data:
                data["CURRENT_BOARD"] = "default" if data["BOARDS"] else None
                dirty = True
                
            if dirty and data.get("NOTION_TOKEN"):
                with open(CONFIG_FILE, "w") as f:
                    json.dump(data, f)
                    
            return data
        except json.JSONDecodeError:
            return None
    return None

def switch_board(alias_or_id: str) -> bool:
    """Sets the active board. Returns True if successful, False if invalid format."""
    cfg = load_config()
    if not cfg: return False
    
    # If it's a known alias
    if alias_or_id in cfg.get("BOARDS", {}):
        cfg["CURRENT_BOARD"] = alias_or_id
        
        # Backward compatibility for api.py calls
        cfg["NOTION_DATABASE_ID"] = cfg["BOARDS"][alias_or_id]
        
    else:
        # Otherwise, treat it as a new URL or raw ID, mapping it to alias: <short_id>
        db_id = extract_notion_id(alias_or_id)
        if not db_id or len(db_id) != 32:
            return False
            
        short_alias = db_id[:6]
        if "BOARDS" not in cfg: cfg["BOARDS"] = {}
        cfg["BOARDS"][short_alias] = db_id
        cfg["CURRENT_BOARD"] = short_alias
        cfg["NOTION_DATABASE_ID"] = db_id

    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)
    return True

def save_config(token: str, db_url: str) -> dict:
    """Saves the token and extracted DB ID to the hidden config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get existing boards if we had them
    existing_cfg = load_config()
    boards = existing_cfg.get("BOARDS", {}) if existing_cfg else {}
    
    db_id = extract_notion_id(db_url)
    
    # Update default board with new setup
    boards["default"] = db_id
    
    config_data = {
        "NOTION_TOKEN": token,
        "NOTION_DATABASE_ID": db_id,
        "CURRENT_BOARD": "default",
        "BOARDS": boards
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)
        
    return config_data