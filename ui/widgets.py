from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import VerticalScroll

class TaskCard(Static, can_focus=True):
    def __init__(self, task_id: str, title: str, status: str, tags: list, description: str, sync_status: str = "synced", due_date: str = None, priority: str = None, assignee: str = None, *args, **kwargs):
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

    def compose(self) -> ComposeResult:
        import datetime
        is_pending = self.sync_status != "synced"
        
        title_text = f"[PENDING] {self.title}" if is_pending else self.title
        yield Static(title_text, classes="task-title")
        
        # Build a single Rich-markup string for the metadata row
        parts = []
        
        if self.priority:
            color = {"High": "red", "Medium": "yellow", "Low": "green"}.get(self.priority, "blue")
            parts.append(f"[bold {color}][{self.priority.upper()}][/]")
        
        if self.due_date:
            try:
                due = datetime.date.fromisoformat(self.due_date.split("T")[0])
                is_overdue = due < datetime.date.today()
                date_str = due.strftime("%b %d")
                color = "red" if is_overdue else "cyan"
                parts.append(f"[{color}]Due: {date_str}[/]")
            except Exception:
                parts.append(f"[cyan]Due: {self.due_date}[/]")
        
        if self.assignee:
            parts.append(f"[magenta]@{self.assignee}[/]")
        
        clean_tags = [t for t in self.tags if t and isinstance(t, str) and t.strip()]
        for tag in clean_tags:
            parts.append(f"[bold blue]#{tag}[/]")
        
        if parts:
            yield Static("  ".join(parts), classes="task-meta")


    def on_mount(self) -> None:
        if self.sync_status != "synced":
            self.add_class("pending")

    def on_click(self) -> None:
        self.focus()

class KanbanColumn(VerticalScroll, can_focus=True): pass
class CommandBar(Input): pass
class SearchBar(Input): pass