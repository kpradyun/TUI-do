import json
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button, Label, Static, TextArea
from textual.containers import Vertical, Horizontal, Center, Middle
from textual import work

class SetupScreen(Screen):
    """Initial configuration screen for Notion Token and Database URL."""
    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("TUI-do Search Setup", classes="dialog-title")
                    yield Static("Enter Notion Integration Secret:", classes="dialog-label")
                    yield Input(placeholder="ntn_...", id="token-input", password=True)
                    yield Static("Enter Notion Database URL:", classes="dialog-label")
                    yield Input(placeholder="https://www.notion.so/...", id="db-input")
                    yield Button("Authenticate Workspace", variant="primary", id="setup-run")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-run":
            token = self.query_one("#token-input", Input).value.strip()
            db_url = self.query_one("#db-input", Input).value.strip()
            if token and db_url:
                import config
                config.save_config(token, db_url)
                self.app.reload_board_data()
                self.app.pop_screen()

class NewTaskScreen(Screen):
    """Modal dialog for creating a new task with metadata."""
    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Create New Task", classes="dialog-title")
                    
                    yield Static("Title", classes="dialog-label")
                    yield Input(placeholder="Task name...", id="task-title")
                    
                    yield Static("Tags (space separated)", classes="dialog-label")
                    yield Input(placeholder="feature bug urgent", id="task-tags")
                    
                    yield Static("Due Date (YYYY-MM-DD)", classes="dialog-label")
                    yield Input(placeholder="2024-12-31", id="task-due")
                    
                    yield Static("Priority (High/Medium/Low)", classes="dialog-label")
                    yield Input(placeholder="High", id="task-priority")
                    
                    yield Static("Assignee Name", classes="dialog-label")
                    yield Input(placeholder="Pradyun", id="task-assignee")
                    
                    yield Static("Description", classes="dialog-label")
                    yield TextArea(id="task-desc")
                    
                    yield Button("Create Task", variant="primary", id="create-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-btn":
            title = self.query_one("#task-title", Input).value.strip()
            tags_str = self.query_one("#task-tags", Input).value.strip()
            due = self.query_one("#task-due", Input).value.strip() or None
            prio = self.query_one("#task-priority", Input).value.strip() or None
            assignee = self.query_one("#task-assignee", Input).value.strip() or None
            desc = self.query_one("#task-desc", TextArea).text
            
            if title:
                tags_list = tags_str.split() if tags_str else []
                self.app.action_create_task(title, tags_list, desc, due, prio, assignee)
                self.app.pop_screen()

    def on_mount(self) -> None:
        self.bind("escape", "app.pop_screen")

class TaskDetailScreen(Screen):
    """View and edit task details, including Notion comments and sub-tasks."""
    def __init__(self, task_card, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_card = task_card

    def compose(self) -> ComposeResult:
        from ui.widgets import TaskCard
        with Center():
            with Middle():
                with Vertical(classes="dialog-box large-dialog"):
                    status_color = "green" if self.task_card.status == "Done" else "yellow"
                    yield Static(f"Task Details [dim]({self.task_card.sync_status})[/]", classes="dialog-title")
                    
                    yield Static("Title", classes="dialog-label")
                    yield Input(value=self.task_card.title, id="dt-title")
                    
                    # Metadata row with property chips
                    chips = []
                    if self.task_card.priority:
                        p = self.task_card.priority.lower()
                        color = "red" if "high" in p else "yellow" if "med" in p else "blue"
                        chips.append(f"[bold {color}]◆ {self.task_card.priority}[/]")
                    if self.task_card.due_date:
                        chips.append(f"[bold cyan]⏰ {self.task_card.due_date.split('T')[0]}[/]")
                    if self.task_card.assignee:
                        chips.append(f"[bold magenta]@ {self.task_card.assignee}[/]")
                    if self.task_card.tags:
                        for tag in self.task_card.tags:
                            chips.append(f"[bold blue]# {tag}[/]")
                    if chips:
                        yield Static("  ".join(chips), id="dt-chips")
                    
                    yield Static("Description", classes="dialog-label")
                    yield TextArea(text=self.task_card.description or "", id="dt-desc")
                    
                    yield Static("Tags (space separated)", classes="dialog-label")
                    yield Input(value=" ".join(self.task_card.tags), id="dt-tags")
                    
                    yield Static("Loading cloud data...", id="dt-loading", classes="dialog-label")
                    yield Vertical(id="dt-subtasks-container", classes="hidden")
                    yield Vertical(id="dt-comments-container", classes="hidden")
                    
                    yield Button("Save Changes", id="dt-save", variant="primary")

    def on_mount(self) -> None:
        self.bind("escape", "app.pop_screen")
        self.load_context()

    @work(thread=True)
    def load_context(self) -> None:
        import api
        try:
            if self.task_card.sync_status == "synced":
                subtasks = api.get_subtasks(self.task_card.task_id)
                comments = api.get_comments(self.task_card.task_id)
                self.app.call_from_thread(self._render_context, subtasks, comments)
            else:
                self.app.call_from_thread(self._render_context, [], [])
        except:
            self.app.call_from_thread(self._render_context, [], [])

    def _render_context(self, subtasks, comments):
        try:
            loading = self.query_one("#dt-loading")
            loading.add_class("hidden")
            
            if subtasks:
                container = self.query_one("#dt-subtasks-container")
                container.remove_children()
                container.remove_class("hidden")
                container.mount(Static("───────────────────────────────", classes="dialog-label"))
                container.mount(Static("[bold cyan]Sub-tasks[/]", classes="dialog-label"))
                for st in subtasks:
                    mark = "[bold green]✔[/][strike]" if st["checked"] else "[white]☐[/]"
                    end = "[/]" if st["checked"] else ""
                    container.mount(Static(f"  {mark} {st['text']}{end}", classes="dt-context-item"))
                    
            if comments:
                container = self.query_one("#dt-comments-container")
                container.remove_children()
                container.remove_class("hidden")
                container.mount(Static("───────────────────────────────", classes="dialog-label"))
                container.mount(Static("[bold cyan]Comments[/]", classes="dialog-label"))
                for c in comments:
                    container.mount(Static(f"  [bold blue]{c['author']}[/]: {c['text']}", classes="dt-context-item"))
        except: pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dt-save":
            new_title = self.query_one("#dt-title", Input).value.strip()
            new_desc = self.query_one("#dt-desc", TextArea).text.strip()
            new_tags_str = self.query_one("#dt-tags", Input).value.strip()
            if new_title:
                new_tags = new_tags_str.split() if new_tags_str else []
                # Update local DB and push
                import db
                db.queue_update(self.task_card.task_id, new_title, self.task_card.status, new_desc, 
                                self.task_card.due_date, self.task_card.priority, self.task_card.assignee)
                # Note: db.queue_update currently doesn't take tags, let's fix that!
                self.app.action_update_task_details(self.task_card, new_title, new_desc, new_tags)
                self.app.pop_screen()

class ConfirmDeleteScreen(Screen):
    """A simple modal asking the user to confirm before archiving a task."""
    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
        ("y", "confirm", "Yes, Delete"),
    ]
    def __init__(self, task_card, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_card = task_card

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Archive Task?", classes="dialog-title")
                    yield Static(f'Archive "{self.task_card.title}"?', classes="dialog-label")
                    yield Static("Press [y] to confirm or [Escape] to cancel.", classes="dialog-label")
                    yield Button("Archive Task", id="del-confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "del-confirm":
            self.action_confirm()

    def action_confirm(self) -> None:
        self.app.action_confirm_delete(self.task_card)
        self.app.pop_screen()

class HelpScreen(Screen):
    """A professional help modal explaining keys and commands."""
    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]
    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box large-dialog"):
                    yield Static("TUI-do Kanban Quick Help", classes="dialog-title")
                    yield Static("[bold cyan]Navigation & Actions[/]")
                    yield Static("  [white]h/j/k/l / Arrows[/]  - Navigate board")
                    yield Static("  [white]Enter[/]             - Edit Task / View Subtasks")
                    yield Static("  [white][ / ][/]             - Move Right / Left")
                    yield Static("  [white]n[/]                 - New Task Dialog")
                    yield Static("  [white]x[/]                 - Archive Focused Task")
                    yield Static("  [white]u[/]                 - Undo Last Action\n")
                    yield Static("[bold cyan]Search & Commands[/]")
                    yield Static("  [white]/[/]                 - Filter by fragment (title, #tag)")
                    yield Static("  [white]:new <title>[/]      - Quick create from command line")
                    yield Static("  [white]:switch <alias>[/]    - Swap between different boards")
                    yield Static("  [white]:export <file>[/]     - Save board to Markdown")
                    yield Static("  [white]:config[/]            - Change Notion token/ID\n")
                    yield Static("[bold cyan]App Control[/]")
                    yield Static("  [white]r[/]                 - Refresh / Full Sync")
                    yield Static("  [white]d[/]                 - Toggle Dark/Light Mode")
                    yield Static("  [white]q[/]                 - Quit Application\n")
                    yield Static("Press [bold red]Escape[/] to close.", classes="dialog-label")
                    yield Button("Close Help", variant="success", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.app.pop_screen()