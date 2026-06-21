from __future__ import annotations

import datetime
from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import VerticalScroll


class TaskCard(Static, can_focus=True):
    """A single Kanban task card."""

    RECURRING_ICONS = {"daily": "↻D", "weekly": "↻W", "monthly": "↻M"}

    def __init__(
        self,
        task_id: str,
        title: str,
        status: str,
        tags: list,
        description: str,
        sync_status: str = "synced",
        due_date: str = None,
        priority: str = None,
        assignee: str = None,
        recurring_interval: str = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.task_id = task_id
        self.title = title
        self.status = status
        self.tags = tags
        self.description = description
        self.sync_status = sync_status
        self.due_date = due_date
        self.priority = priority
        self.assignee = assignee
        self.recurring_interval = recurring_interval

    def compose(self) -> ComposeResult:
        is_pending = self.sync_status != "synced"
        title_text = f"[PENDING] {self.title}" if is_pending else self.title
        title_cls = "task-title done-title" if self.status == "Done" else "task-title"
        yield Static(title_text, classes=title_cls)

        parts = []

        if self.priority:
            color = {"High": "red", "Medium": "yellow", "Low": "green"}.get(self.priority, "blue")
            parts.append(f"[bold {color}][{self.priority.upper()}][/]")

        if self.due_date:
            try:
                due = datetime.date.fromisoformat(self.due_date.split("T")[0])
                date_str = due.strftime("%b %d")
                color = "red" if due < datetime.date.today() and self.status != "Done" else "cyan"
                parts.append(f"[{color}]Due: {date_str}[/]")
            except Exception:
                parts.append(f"[cyan]Due: {self.due_date}[/]")

        if self.assignee:
            parts.append(f"[magenta]@{self.assignee}[/]")

        clean_tags = [t for t in self.tags if t and isinstance(t, str) and t.strip()]
        for tag in clean_tags:
            parts.append(f"[bold blue]#{tag}[/]")

        if self.recurring_interval:
            icon = self.RECURRING_ICONS.get(self.recurring_interval, "↻")
            parts.append(f"[bold yellow]{icon}[/]")

        if parts:
            yield Static("  ".join(parts), classes="task-meta")

    def on_mount(self) -> None:
        if self.sync_status != "synced":
            self.add_class("pending")
        if self.due_date and self.status != "Done":
            try:
                due = datetime.date.fromisoformat(self.due_date.split("T")[0])
                if due < datetime.date.today():
                    self.add_class("overdue-card")
            except Exception:
                pass

    def on_click(self) -> None:
        self.focus()

    def toggle_selected(self) -> bool:
        """Toggle the visual selected state. Returns the new selected state."""
        if self.has_class("selected"):
            self.remove_class("selected")
            return False
        else:
            self.add_class("selected")
            return True


class KanbanColumn(VerticalScroll, can_focus=True):
    pass


class CommandBar(Input):
    pass


class SearchBar(Input):
    pass
