from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Center, Middle, Vertical
from textual.widgets import Static, Input, Button, TextArea
import config
from ui.widgets import TaskCard

class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("⚙️ TUI-do Configuration", classes="dialog-title")
                    yield Static("Notion Integration Secret:")
                    yield Input(placeholder="secret_...", id="token-input", password=True)
                    yield Static("Notion Database URL:")
                    yield Input(placeholder="https://notion.so/...", id="db-input")
                    yield Button("Authenticate Workspace", id="save-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            token = self.query_one("#token-input", Input).value.strip()
            db_url = self.query_one("#db-input", Input).value.strip()
            if token and db_url:
                config.save_config(token, db_url)
                self.app.pop_screen()
                self.app.load_board_data()

class NewTaskScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Cancel")]
    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box large-dialog"):
                    yield Static("✨ Create New Task", classes="dialog-title")
                    yield Input(placeholder="Task Title", id="nt-title")
                    yield Input(placeholder="Tags (comma separated)", id="nt-tags")
                    yield Static("Task Description:", classes="dialog-label")
                    yield TextArea(id="nt-desc")
                    yield Button("Create Task", id="nt-save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "nt-save":
            title = self.query_one("#nt-title", Input).value.strip()
            tags_raw = self.query_one("#nt-tags", Input).value.strip()
            desc = self.query_one("#nt-desc", TextArea).text.strip()
            if title:
                tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
                self.app.action_create_task(title, tags_list, desc)
                self.app.pop_screen()

class TaskDetailScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Cancel")]
    def __init__(self, task_card: TaskCard, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_card = task_card

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box large-dialog"):
                    yield Static("📝 Edit Task Details", classes="dialog-title")
                    yield Input(value=self.task_card.title, id="dt-title")
                    yield Static("Task Description:", classes="dialog-label")
                    yield TextArea(text=self.task_card.description, id="dt-desc")
                    yield Button("Save Changes", id="dt-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dt-save":
            new_title = self.query_one("#dt-title", Input).value.strip()
            new_desc = self.query_one("#dt-desc", TextArea).text.strip()
            if new_title:
                self.app.action_update_task_details(self.task_card, new_title, new_desc)
                self.app.pop_screen()