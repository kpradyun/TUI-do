import re
import socket
from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input
from textual.binding import Binding
from textual import work

import config
import db
import api  # <--- Our new sync engine
from ui.widgets import TaskCard, KanbanColumn, CommandBar, SearchBar
from ui.screens import SetupScreen, NewTaskScreen, TaskDetailScreen

def check_internet_connection() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False

class TuiDoApp(App):
    CSS_PATH = None # We keep CSS in the string for now for simplicity
    CSS = """
    Screen { layout: vertical; background: $background; }
    #board-container { layout: horizontal; height: 1fr; align: center middle; padding: 1 2; }
    KanbanColumn { width: 1fr; height: 100%; border: solid $surface-darken-1; margin: 0 1; background: $panel; }
    KanbanColumn:focus-within { border: thick $accent; } 
    TaskCard { width: 100%; height: auto; padding: 1 2; margin: 1; background: $surface; border-left: thick $surface-lighten-2; color: $text; }
    TaskCard:hover { background: $surface-lighten-1; border-left: thick $success; }
    TaskCard:focus { border-left: thick $accent; background: $surface-lighten-2; }
    .task-title { text-style: bold; margin-bottom: 1; }
    .hidden { display: none; }
    .tag-container { height: auto; }
    .tag { background: $primary; color: $background; text-style: bold; margin-right: 1; padding: 0 1; }
    .dialog-box { width: 60; height: auto; padding: 2 4; border: tall $accent; background: $surface; }
    .large-dialog { width: 80; height: auto; }
    .dialog-title { content-align: center middle; text-style: bold; margin-bottom: 2; color: $primary;}
    .dialog-label { margin-top: 1; margin-bottom: 1; color: $text-muted; }
    Input { margin-bottom: 1; }
    TextArea { height: 12; margin-bottom: 2; border: round $primary; background: $panel; }
    TextArea:focus { border: round $accent; }
    Button { width: 100%; margin-top: 1; }
    CommandBar { dock: bottom; display: none; background: $surface-darken-1; border-top: solid $accent; text-style: bold; padding: 0 1; }
    CommandBar.-visible { display: block; }
    SearchBar { dock: top; display: none; background: $surface-darken-1; border-bottom: solid $warning; text-style: bold; padding: 0 1; }
    SearchBar.-visible { display: block; }
    """

    BINDINGS = [
        ("d", "toggle_dark", "Theme"),
        ("q", "quit", "Quit"),
        Binding("escape", "escape_menus", "Cancel", show=False),
        Binding("]", "move_right", "Move Right"),
        Binding("[", "move_left", "Move Left"),
        Binding("n", "push_new_task", "New Task"),
        Binding("enter", "open_task_details", "Edit Details"),
        Binding("x", "delete_task", "Archive"),
        Binding("colon", "open_command_bar", "Command Palette", key_display=":"),
        Binding("/", "open_search_bar", "Filter Cards", key_display="/"),
        Binding("j", "focus_down", "Down", show=False),
        Binding("down", "focus_down", "Down", show=False),
        Binding("k", "focus_up", "Up", show=False),
        Binding("up", "focus_up", "Up", show=False),
        Binding("h", "focus_left", "Left", show=False),
        Binding("left", "focus_left", "Left", show=False),
        Binding("l", "focus_right", "Right", show=False),
        Binding("right", "focus_right", "Right", show=False),
    ]

    def on_mount(self) -> None:
        self.title = "TUI-do Kanban"
        self.is_online = check_internet_connection()
        db.init_db()
        
        user_config = config.load_config()
        if not user_config: 
            self.push_screen(SetupScreen())
        else: 
            self.load_board_data()
            
        self.set_interval(5.0, self.monitor_network_status)

    @work(thread=True)
    def monitor_network_status(self) -> None:
        currently_online = check_internet_connection()
        if currently_online and not self.is_online:
            self.is_online = True
            self.call_from_thread(self.notify, "🟢 Online: Syncing pending changes...")
            self.background_full_sync()
        elif not currently_online and self.is_online:
            self.is_online = False
            self.call_from_thread(self.notify, "🔴 Offline: Using local cache.", severity="warning")
            def update_title(): self.sub_title = "Offline Mode"
            self.call_from_thread(update_title)

    def load_board_data(self) -> None:
        """Instantly loads from SQLite."""
        self.tasks_data = db.get_all_local_tasks()
        
        # UI Mounting
        self.mount(Header(show_clock=True))
        self.mount(SearchBar(id="search-bar", placeholder="Type to filter..."))
        self.board_container = Horizontal(id="board-container")
        self.mount(self.board_container)
        
        self.columns = {
            "Not started": KanbanColumn(id="todo-col"),
            "In progress": KanbanColumn(id="inprogress-col"),
            "Done": KanbanColumn(id="done-col")
        }
        for name, col in self.columns.items():
            col.border_title = name.upper()
            self.board_container.mount(col)

        self.refresh_ui_from_local_db()
        
        self.mount(CommandBar(id="cmd-bar"))
        self.mount(Footer())
        self.call_after_refresh(self.columns["Not started"].focus)

        if self.is_online:
            self.background_full_sync()

    def refresh_ui_from_local_db(self):
        """Redraws task cards based on whatever is currently in SQLite."""
        self.tasks_data = db.get_all_local_tasks()
        for status, col in self.columns.items():
            col.remove_children()
            for task in self.tasks_data.get(status, []):
                col.mount(TaskCard(
                    task_id=task["id"], 
                    title=task["name"], 
                    status=status, 
                    tags=task["tags"], 
                    description=task["desc"]
                ))

    @work(thread=True)
    def background_full_sync(self) -> None:
        """Pushes local edits, pulls cloud changes, then refreshes UI."""
        if not self.is_online: return
        
        self.sub_title = "Syncing..."
        success = api.full_sync()
        
        if success:
            self.call_from_thread(self.refresh_ui_from_local_db)
            def set_title(): self.sub_title = "🟢 Synced"
            self.call_from_thread(set_title)
        else:
            def set_err(): self.sub_title = "⚠️ Sync Error"
            self.call_from_thread(set_err)

    # --- INPUT & NAVIGATION ---
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.control.id == "search-bar":
            query = event.value.lower().strip()
            for card in self.query(TaskCard):
                visible = not query or query in card.title.lower() or any(query in t.lower() for t in card.tags)
                card.set_class(not visible, "hidden")

    def action_escape_menus(self) -> None:
        for widget_id in ["#cmd-bar", "#search-bar"]:
            w = self.query_one(widget_id)
            w.remove_class("-visible")
            if widget_id == "#search-bar": w.value = ""
        self.columns["Not started"].focus()

    def action_open_search_bar(self) -> None:
        self.query_one("#search-bar").add_class("-visible")
        self.query_one("#search-bar").focus()

    # --- CRUD ACTIONS (All talking to DB first) ---
    def action_create_task(self, title: str, tags: list, desc: str) -> None:
        temp_id = f"local_{hash(title)}"
        db.queue_create(temp_id, title, "Not started", tags, desc)
        self.refresh_ui_from_local_db()
        self.background_full_sync()

    def action_move_right(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            flow = {"Not started": "In progress", "In progress": "Done"}
            if card.status in flow:
                db.queue_update(card.task_id, card.title, flow[card.status], card.description)
                self.refresh_ui_from_local_db()
                self.background_full_sync()

    def action_move_left(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            flow = {"Done": "In progress", "In progress": "Not started"}
            if card.status in flow:
                db.queue_update(card.task_id, card.title, flow[card.status], card.description)
                self.refresh_ui_from_local_db()
                self.background_full_sync()

    def action_update_task_details(self, card, new_title, new_desc):
        db.queue_update(card.task_id, new_title, card.status, new_desc)
        self.refresh_ui_from_local_db()
        self.background_full_sync()

    def action_delete_task(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            db.queue_delete(card.task_id)
            self.refresh_ui_from_local_db()
            self.background_full_sync()

    # --- BOILERPLATE FOR MODALS & VIM NAV ---
    def action_push_new_task(self): self.push_screen(NewTaskScreen())
    def action_open_task_details(self):
        if isinstance(self.focused, TaskCard): self.push_screen(TaskDetailScreen(self.focused))
    def action_open_command_bar(self):
        c = self.query_one("#cmd-bar")
        c.add_class("-visible")
        c.value = ":"
        c.focus()
        c.cursor_position = 1

    def on_input_submitted(self, event: Input.Submitted):
        if event.control.id == "cmd-bar":
            cmd = event.value.strip()
            self.action_escape_menus()
            if cmd.startswith(":new "):
                content = cmd[5:]
                tags = re.findall(r'#(\w+)', content)
                title = re.sub(r'#\w+', '', content).strip()
                self.action_create_task(title, tags, "")
            elif cmd in (":q", ":quit"): self.exit()
            elif cmd == ":refresh": self.background_full_sync()
            elif cmd in (":rm", ":del"): self.action_delete_task()

    def action_focus_down(self):
        if isinstance(self.focused, TaskCard):
            sibs = [s for s in self.focused.parent.query(TaskCard) if not s.has_class("hidden")]
            if self.focused in sibs:
                idx = sibs.index(self.focused)
                if idx < len(sibs)-1: sibs[idx+1].focus()

    def action_focus_up(self):
        if isinstance(self.focused, TaskCard):
            sibs = [s for s in self.focused.parent.query(TaskCard) if not s.has_class("hidden")]
            if self.focused in sibs:
                idx = sibs.index(self.focused)
                if idx > 0: sibs[idx-1].focus()

    def action_focus_left(self):
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        cols = list(self.query(KanbanColumn))
        idx = cols.index(col)
        if idx > 0:
            prev = cols[idx-1]
            cards = [c for c in prev.query(TaskCard) if not c.has_class("hidden")]
            (cards[0].focus() if cards else prev.focus())

    def action_focus_right(self):
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        cols = list(self.query(KanbanColumn))
        idx = cols.index(col)
        if idx < len(cols)-1:
            nxt = cols[idx+1]
            cards = [c for c in nxt.query(TaskCard) if not c.has_class("hidden")]
            (cards[0].focus() if cards else nxt.focus())