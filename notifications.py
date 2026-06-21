"""Cross-platform desktop notifications for TUI-do due-date reminders."""
from __future__ import annotations

import datetime


def _notify(title: str, message: str) -> bool:
    """Send a desktop notification via plyer. Returns True on success."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="TUI-do",
            timeout=10,
        )
        return True
    except Exception:
        return False


def check_and_notify() -> None:
    """
    Called once on startup. Fires a single OS notification if there are
    overdue tasks or tasks due today, so the user doesn't miss deadlines.
    """
    try:
        import db
        stats = db.get_stats()
        today = datetime.date.today().isoformat()

        conn = db.get_connection()
        cursor = conn.cursor()
        board_id = db.get_current_board_id()
        cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND status != 'Done' "
            "AND sync_status != 'pending_delete' AND (board_id = ? OR board_id IS NULL)",
            (today, board_id),
        )
        due_today = cursor.fetchone()[0]
        conn.close()

        parts = []
        if stats["overdue"]:
            parts.append(f"{stats['overdue']} overdue")
        if due_today:
            parts.append(f"{due_today} due today")

        if parts:
            _notify("TUI-do Reminder", "  |  ".join(parts))
    except Exception:
        pass  # Notifications are non-critical — never crash the app
