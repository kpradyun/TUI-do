import re
import uuid
import socket
import os
from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input
from textual.binding import Binding
from textual import work

import config
import db
import api
from ui.widgets import TaskCard, KanbanColumn, CommandBar, SearchBar
from ui.screens import SetupScreen, NewTaskScreen, TaskDetailScreen, ConfirmDeleteScreen, HelpScreen

def check_internet_connection() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1.5)
        return True
    except OSError:
        return False

class TuiDoApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("d", "toggle_dark", "Theme"),
        ("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "escape_menus", "Cancel", show=False),
        Binding("]", "move_right", "Move Right"),
        Binding("[", "move_left", "Move Left"),
        Binding("n", "push_new_task", "New Task"),
        Binding("enter", "open_task_details", "Edit Details"),
        Binding("x", "delete_task", "Archive"),
        Binding("colon", "open_command_bar", "Command Palette", key_display=":"),
        Binding("/", "open_search_bar", "Filter Cards", key_display="/"),
        Binding("u", "undo", "Undo"),
        Binding("j", "focus_down", "Down", show=False),
        Binding("down", "focus_down", "Down", show=False),
        Binding("k", "focus_up", "Up", show=False),
        Binding("up", "focus_up", "Up", show=False),
        Binding("h", "focus_left", "Left", show=False),
        Binding("left", "focus_left", "Left", show=False),
        Binding("l", "focus_right", "Right", show=False),
        Binding("right", "focus_right", "Right", show=False),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def on_mount(self) -> None:
        self.title = "TUI-do Kanban"
        self.is_online = check_internet_connection()
        self.undo_stack = []
        db.init_db()

        user_config = config.load_config()
        if not user_config:
            self.push_screen(SetupScreen())
        else:
            self.load_board_data()

        self.set_interval(10.0, self.monitor_network_status)
        self.set_interval(60.0, self.background_full_sync)

    @work(thread=True)
    def monitor_network_status(self) -> None:
        currently_online = check_internet_connection()
        if currently_online and not self.is_online:
            self.is_online = True
            self.call_from_thread(self.notify, "Online: Syncing pending changes...")
            self.background_full_sync()
        elif not currently_online and self.is_online:
            self.is_online = False
            self.call_from_thread(self.notify, "Offline: Using local cache.", severity="warning")
            def update_title(): self.sub_title = "Offline Mode"
            self.call_from_thread(update_title)

    def load_board_data(self) -> None:
        """Mounts the board skeleton and loads tasks from SQLite."""
        self.tasks_data = db.get_all_local_tasks()
        
        self.mount(Header(show_clock=True))
        self.mount(SearchBar(id="search-bar", placeholder="Search by title, #tag, due:today, assignee:name..."))
        self.board_container = Horizontal(id="board-container")
        self.mount(self.board_container)

        self.columns = {
            "Not started": KanbanColumn(id="todo-col"),
            "In progress": KanbanColumn(id="inprogress-col"),
            "Done": KanbanColumn(id="done-col")
        }
        for name, col in self.columns.items():
            lab = name.upper() if name != "Not started" else "TODO"
            col.border_title = f"{lab}"
            self.board_container.mount(col)

        self.refresh_ui_from_local_db()

        self.mount(CommandBar(id="cmd-bar"))
        self.mount(Footer())
        self.call_after_refresh(lambda: self.columns["Not started"].focus())

        if self.is_online:
            self.background_full_sync()

    def reload_board_data(self) -> None:
        """Tears down the existing board widgets and remounts. Used after :config or :switch."""
        api.clear_cache()
        for widget_id in ("#search-bar", "#board-container", "#cmd-bar"):
            try: self.query_one(widget_id).remove()
            except: pass
        for cls in (Header, Footer):
            try: self.query(cls).first().remove()
            except: pass
        self.call_after_refresh(self.load_board_data)

    def refresh_ui_from_local_db(self):
        """Redraws task cards and updates column count badges from SQLite."""
        self.tasks_data = db.get_all_local_tasks()

        COLUMN_LABELS = {"Not started": "TODO", "In progress": "IN PROGRESS", "Done": "DONE"}
        for status, col in self.columns.items():
            if not col.is_mounted: continue
            col.remove_children()
            tasks = self.tasks_data.get(status, [])
            label = COLUMN_LABELS.get(status, status.upper())
            col.border_title = f"{label} ({len(tasks)})"
            for task in tasks:
                col.mount(TaskCard(
                    task_id=task["id"],
                    title=task["name"],
                    status=status,
                    tags=task["tags"],
                    description=task["desc"],
                    sync_status=task["sync_status"],
                    due_date=task.get("due_date"),
                    priority=task.get("priority"),
                    assignee=task.get("assignee")
                ))

    @work(thread=True)
    def background_full_sync(self) -> None:
        """Pushes local edits, pulls cloud changes, then refreshes UI."""
        if not self.is_online: return
        def set_syncing(): self.sub_title = "Syncing..."
        self.call_from_thread(set_syncing)
        
        success = api.full_sync()

        if success:
            self.call_from_thread(self.refresh_ui_from_local_db)
            def set_title(): self.sub_title = "Synced"
            self.call_from_thread(set_title)
        else:
            def set_err(): self.sub_title = "Sync Error"
            self.call_from_thread(set_err)

    # --- INPUT & NAVIGATION ---
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.control.id == "search-bar":
            query_str = event.value.lower().strip()
            import datetime
            today = datetime.date.today()
            
            fragments = query_str.split()
            
            for card in self.query(TaskCard):
                if not fragments:
                    card.remove_class("hidden")
                    continue
                
                matches_all = True
                for frag in fragments:
                    if frag.startswith("due:"):
                        val = frag[4:].strip()
                        if not card.due_date:
                            matches_all = False
                            break
                        try:
                            due = datetime.date.fromisoformat(card.due_date.split("T")[0])
                            if val == "today":
                                if not (due == today): matches_all = False
                            elif val == "overdue":
                                if not (due < today): matches_all = False
                            else:
                                if not (val in card.due_date.lower()): matches_all = False
                        except:
                            if not (val in card.due_date.lower()): matches_all = False
                    elif frag.startswith("assignee:"):
                        val = frag[9:].strip()
                        if not (card.assignee and val in card.assignee.lower()):
                            matches_all = False
                    elif frag.startswith("priority:"):
                        val = frag[9:].strip()
                        if not (card.priority and val in card.priority.lower()):
                            matches_all = False
                    else:
                        matches_title = frag in card.title.lower()
                        matches_tags = any(frag in t.lower() for t in card.tags)
                        if not (matches_title or matches_tags):
                            matches_all = False
                    
                    if not matches_all: break
                
                card.set_class(not matches_all, "hidden")

    def action_escape_menus(self) -> None:
        for widget_id in ["#cmd-bar", "#search-bar"]:
            try:
                w = self.query_one(widget_id)
                w.remove_class("-visible")
                if widget_id == "#search-bar":
                    w.value = ""
                    for card in self.query(TaskCard): card.remove_class("hidden")
            except: pass
        try: self.columns["Not started"].focus()
        except: pass

    def action_open_search_bar(self) -> None:
        try:
            s = self.query_one("#search-bar")
            s.add_class("-visible")
            s.focus()
        except: pass

    # --- CRUD ACTIONS ---
    def action_create_task(self, title: str, tags: list, desc: str, due_date: str = None, priority: str = None, assignee: str = None) -> None:
        temp_id = f"local_{uuid.uuid4().hex}"
        db.queue_create(temp_id, title, "Not started", tags, desc, due_date, priority, assignee)
        self.refresh_ui_from_local_db()
        self.background_full_sync()

    def action_move_right(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            flow = {"Not started": "In progress", "In progress": "Done"}
            if card.status in flow:
                new_status = flow[card.status]
                self.undo_stack.append({
                    "type": "move", "task_id": card.task_id, "title": card.title, "desc": card.description,
                    "from": card.status, "to": new_status, "due_date": card.due_date,
                    "priority": card.priority, "assignee": card.assignee, "tags": card.tags
                })
                db.queue_update(card.task_id, card.title, new_status, card.description, card.due_date, card.priority, card.assignee)
                self.refresh_ui_from_local_db()
                self.background_full_sync()

    def action_move_left(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            flow = {"Done": "In progress", "In progress": "Not started"}
            if card.status in flow:
                new_status = flow[card.status]
                self.undo_stack.append({
                    "type": "move", "task_id": card.task_id, "title": card.title, "desc": card.description,
                    "from": card.status, "to": new_status, "due_date": card.due_date,
                    "priority": card.priority, "assignee": card.assignee, "tags": card.tags
                })
                db.queue_update(card.task_id, card.title, new_status, card.description, card.due_date, card.priority, card.assignee)
                self.refresh_ui_from_local_db()
                self.background_full_sync()

    def action_undo(self) -> None:
        if not self.undo_stack:
            self.notify("Nothing to undo.", severity="warning")
            return
            
        action = self.undo_stack.pop()
        type = action.get("type", "move")
        
        if type == "delete":
            is_offline = action["task_id"].startswith("local_")
            if is_offline:
                db.queue_create(action["task_id"], action["title"], action["status"], action["tags"], 
                                action["desc"], action["due_date"], action["priority"], action["assignee"])
            else:
                db.queue_update(action["task_id"], action["title"], action["status"], action["desc"],
                                action["due_date"], action["priority"], action["assignee"])
            self.notify(f"Undo: Restored task '{action['title']}'")
        else:
            db.queue_update(action["task_id"], action["title"], action["from"], action["desc"],
                            action.get("due_date"), action.get("priority"), action.get("assignee"), action.get("tags"))
            self.notify(f"Undo: Moved back to {action['from']}")

        self.refresh_ui_from_local_db()

    def action_update_task_details(self, card, new_title, new_desc, new_tags: list = None):
        db.queue_update(card.task_id, new_title, card.status, new_desc, card.due_date, card.priority, card.assignee, new_tags)
        self.refresh_ui_from_local_db()
        self.background_full_sync()

    def action_delete_task(self) -> None:
        card = self.focused
        if isinstance(card, TaskCard):
            self.push_screen(ConfirmDeleteScreen(card))

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_confirm_delete(self, card: TaskCard) -> None:
        self.undo_stack.append({
            "type": "delete", "task_id": card.task_id, "title": card.title, "status": card.status,
            "desc": card.description, "tags": card.tags, "due_date": card.due_date,
            "priority": card.priority, "assignee": card.assignee,
        })
        db.queue_delete(card.task_id)
        self.refresh_ui_from_local_db()
        self.background_full_sync()

    def action_push_new_task(self): self.push_screen(NewTaskScreen())

    def action_open_task_details(self):
        if isinstance(self.focused, TaskCard):
            self.push_screen(TaskDetailScreen(self.focused))

    def action_open_command_bar(self):
        try:
            c = self.query_one("#cmd-bar")
            c.add_class("-visible")
            c.value = ":"
            c.focus()
            c.cursor_position = 1
        except: pass

    def action_refresh(self) -> None:
        if self.is_online: self.background_full_sync()
        else: self.notify("Offline — can't sync.", severity="warning")

    def on_input_submitted(self, event: Input.Submitted):
        if event.control.id == "cmd-bar":
            cmd = event.value.strip()
            self.action_escape_menus()
            try:
                if cmd.startswith(":new "):
                    content = cmd[5:]
                    tags = re.findall(r'#(\w+)', content)
                    title = re.sub(r'#\w+', '', content).strip()
                    if title: self.action_create_task(title, tags, "")
                elif cmd in (":q", ":quit"):
                    self.exit()
                elif cmd in (":refresh", ":r"):
                    self.background_full_sync()
                elif cmd in (":rm", ":del"):
                    self.action_delete_task()
                elif cmd == ":config":
                    self.push_screen(SetupScreen())
                elif cmd.startswith(":switch "):
                    target = cmd[8:].strip()
                    if config.switch_board(target):
                        self.notify(f"Switched to board: {target}")
                        self.reload_board_data()
                    else:
                        self.notify("Invalid board alias or URL.", severity="error")
                elif cmd.startswith(":export"):
                    parts = cmd.split(" ", 1)
                    filename = parts[1].strip() if len(parts) > 1 else "export.md"
                    self.action_export_markdown(filename)
                elif cmd == ":help":
                    self.action_help()
                elif cmd == ":boards":
                    cfg = config.load_config()
                    boards = cfg.get("BOARDS", {})
                    current = cfg.get("CURRENT_BOARD")
                    msg = "[bold cyan]Saved Boards:[/]\n"
                    for alias, db_id in boards.items():
                        mark = "[bold green]▶[/] " if alias == current else "  "
                        msg += f"{mark}[white]{alias}[/] (ID: {db_id[:8]}...)\n"
                    msg += "\nUse [italic]:switch <alias>[/] to swap."
                    self.notify(msg, title="Your Boards", timeout=8)
                else:
                    self.notify(f"Unknown command: {cmd}", severity="error")
            except Exception as e:
                self.notify(f"Command Error: {str(e)}", severity="error")

    def action_export_markdown(self, filename: str) -> None:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("# TUI-do Export\n\n")
                for status in ["Not started", "In progress", "Done"]:
                    tasks = self.tasks_data.get(status, [])
                    if not tasks: continue
                    f.write(f"## {status.upper()}\n\n")
                    for t in tasks:
                        f.write(f"- {'[x]' if status == 'Done' else '[ ]'} **{t['name']}**")
                        if t.get('assignee'): f.write(f" (@{t['assignee']})")
                        f.write("\n")
            self.notify(f"Exported to {filename}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

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
            cards = [c for c in cols[idx-1].query(TaskCard) if not c.has_class("hidden")]
            (cards[0].focus() if cards else cols[idx-1].focus())

    def action_focus_right(self):
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        cols = list(self.query(KanbanColumn))
        idx = cols.index(col)
        if idx < len(cols)-1:
            cards = [c for c in cols[idx+1].query(TaskCard) if not c.has_class("hidden")]
            (cards[0].focus() if cards else cols[idx+1].focus())
