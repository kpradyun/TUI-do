from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import Horizontal, VerticalScroll

class TaskCard(Static, can_focus=True):
    def __init__(self, task_id: str, title: str, status: str, tags: list, description: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_id = task_id  
        self.title = title
        self.status = status
        self.tags = tags
        self.description = description

    def compose(self) -> ComposeResult:
        yield Static(f"{self.title}", classes="task-title")
        clean_tags = [t for t in self.tags if t and isinstance(t, str) and t.strip()]
        if clean_tags:
            tag_container = Horizontal(classes="tag-container")
            with tag_container:
                for tag in clean_tags: yield Static(f" {tag} ", classes="tag")

    def on_click(self) -> None:
        self.focus()

class KanbanColumn(VerticalScroll, can_focus=True): pass
class CommandBar(Input): pass
class SearchBar(Input): pass