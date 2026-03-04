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
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None

def save_config(token: str, db_url: str) -> dict:
    """Saves the token and extracted DB ID to the hidden config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    db_id = extract_notion_id(db_url)
    config_data = {
        "NOTION_TOKEN": token,
        "NOTION_DATABASE_ID": db_id
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)
        
    return config_data