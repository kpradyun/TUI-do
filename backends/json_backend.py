"""
JSON file sync backend.

Syncs tasks to/from a plain JSON file at a configurable path.
Great for teams sharing a Dropbox / Google Drive / OneDrive folder,
or for single users who want a portable, human-readable backup.

Configure the sync file path with:
    :backend json /path/to/shared/tuido_sync.json
"""
from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path

import config
import db
from backends.base import SyncBackend


class JSONBackend(SyncBackend):
    """Reads and writes tasks to a shared JSON file."""

    @property
    def name(self) -> str:
        return "json"

    def _path(self) -> Path:
        return Path(config.get_json_sync_path())

    def is_available(self) -> bool:
        return self._path().parent.exists()

    def full_sync(self) -> bool:
        try:
            path = self._path()
            pending = db.get_pending_tasks()

            # Load existing remote state
            remote: dict[str, dict] = {}
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for t in data.get("tasks", []):
                    remote[t["id"]] = t

            # Apply local pending operations onto the remote snapshot
            for task in pending:
                tid = task["id"]
                status = task["sync_status"]
                tags = json.loads(task["tags"]) if task["tags"] else []

                if status == "pending_create":
                    remote[tid] = {
                        "id": tid,
                        "name": task["title"],
                        "status": task["status"],
                        "tags": tags,
                        "desc": task["description"] or "",
                        "due_date": task["due_date"],
                        "priority": task["priority"],
                        "assignee": task["assignee"],
                    }
                    db.mark_synced(tid)

                elif status == "pending_update":
                    if tid in remote:
                        remote[tid].update({
                            "name": task["title"],
                            "status": task["status"],
                            "desc": task["description"] or "",
                            "due_date": task["due_date"],
                            "priority": task["priority"],
                            "assignee": task["assignee"],
                        })
                    db.mark_synced(tid)

                elif status == "pending_delete":
                    remote.pop(tid, None)
                    db.hard_delete(tid)

            # Write the merged state back to the JSON file atomically
            out = list(remote.values())
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"tasks": out, "last_sync": datetime.datetime.now().isoformat()},
                    f, indent=2,
                )
            tmp.replace(path)  # atomic rename — crash-safe

            # Pull the merged state into the local SQLite cache
            db.save_tasks_from_cloud(out)
            return True

        except Exception:
            return False
