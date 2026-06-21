"""
TUI-do entry point.

Install and run with:
    pip install .
    tuido

Or directly:
    python main.py
"""
from __future__ import annotations


def run() -> None:
    """Main entry point registered by pyproject.toml as the `tuido` CLI command."""
    import db
    import theme
    import notifications
    from ui.app import TuiDoApp

    # ── startup tasks (fast, non-blocking) ────────────────────────────────────
    db.init_db()

    # Spawn fresh copies of any completed recurring tasks that are due today
    spawned = db.process_recurring_tasks()

    # Write a default theme file on first run so the user has something to edit
    theme.write_defaults()

    # Send OS desktop notification for overdue / due-today tasks
    notifications.check_and_notify()

    # ── inject custom theme CSS before the app starts ─────────────────────────
    overrides = theme.load()
    if overrides:
        extra_css = theme.build_css(overrides)
        if extra_css:
            TuiDoApp.CSS = extra_css

    # ── launch ────────────────────────────────────────────────────────────────
    app = TuiDoApp()
    app.run()

    if spawned:
        print(f"[tuido] {spawned} recurring task(s) were reset for the new period.")


if __name__ == "__main__":
    run()
