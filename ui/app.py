import re
import uuid
import socket
from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input, Static
from textual.binding import Binding
from textual import work

import config
import db
from ui.widgets import TaskCard, KanbanColumn, CommandBar, SearchBar
from ui.screens import (
    SetupScreen, NewTaskScreen, TaskDetailScreen, ConfirmDeleteScreen,
    ConfirmBulkDeleteScreen, HelpScreen, PendingQuitScreen, StatsScreen,
    WipScreen, BackendScreen, CommandPaletteScreen,
)

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
        Binding("s", "sort", "Sort Column"),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("ctrl+a", "select_all", "Select All", show=False),
        Binding("colon", "open_command_bar", "Commands", key_display=":"),
        Binding("/", "open_search_bar", "Search", key_display="/"),
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
        self._col_sort: dict[str, str] = {}
        self._selected: set[str] = set()
        self._sync_status: str = ""
        db.init_db()

        user_config = config.load_config()
        if not user_config:
            self.push_screen(SetupScreen())
        else:
            self.load_board_data()

        self.set_interval(10.0, self.monitor_network_status)
        self.set_interval(60.0, self.background_full_sync)

    # ── helpers ───────────────────────────────────────────────────────────────

    @work(thread=True)
    def monitor_network_status(self) -> None:
        if config.is_local_only():
            return
        currently_online = check_internet_connection()
        if currently_online and not self.is_online:
            self.is_online = True
            self.call_from_thread(self.notify, "Online: Syncing pending changes...")
            self.background_full_sync()
        elif not currently_online and self.is_online:
            self.is_online = False
            self.call_from_thread(self.notify, "Offline: Using local cache.", severity="warning")
            def _set(): self._set_sync_status("Offline")
            self.call_from_thread(_set)

    def _get_backend(self):
        from backends import get_backend
        return get_backend()

    def _get_board_statuses(self) -> list[str]:
        from_db = set(db.get_unique_statuses())
        standard = ["Not started", "In progress", "Done"]
        result = list(standard)
        result += [s for s in from_db if s not in standard]
        return result

    def _sort_tasks(self, tasks: list, mode: str) -> list:
        PRIO = {"High": 0, "Medium": 1, "Low": 2}
        if mode == "name":
            return sorted(tasks, key=lambda t: t["name"].lower())
        elif mode == "due":
            return sorted(tasks, key=lambda t: (t.get("due_date") is None, t.get("due_date") or ""))
        elif mode == "priority":
            return sorted(tasks, key=lambda t: PRIO.get(t.get("priority"), 3))
        return tasks

    def _set_sync_status(self, status: str) -> None:
        self._sync_status = status
        self._refresh_subtitle()

    def _refresh_subtitle(self) -> None:
        parts = []
        if self._selected:
            n = len(self._selected)
            parts.append(f"{n} selected  ·  Space=toggle  Ctrl+A=all  x=archive  Esc=clear")
        if self._sync_status:
            parts.append(self._sync_status)
        self.sub_title = "  |  ".join(parts)

    def _update_selection_subtitle(self) -> None:
        self._refresh_subtitle()

    # ── board lifecycle ───────────────────────────────────────────────────────

    def load_board_data(self) -> None:
        self.tasks_data = db.get_all_local_tasks()
        self.mount(Header(show_clock=True))
        self.mount(SearchBar(id="search-bar", placeholder="Search: title  #tag  due:today  assignee:name  priority:high"))
        self.board_container = Horizontal(id="board-container")
        self.mount(self.board_container)

        self.columns: dict[str, KanbanColumn] = {}
        for status in self._get_board_statuses():
            col_id = "col-" + re.sub(r'[^a-z0-9]+', '-', status.lower()).strip('-')
            col = KanbanColumn(id=col_id)
            self.columns[status] = col
            self.board_container.mount(col)

        self.refresh_ui_from_local_db()
        self.mount(CommandBar(id="cmd-bar"))
        self.mount(Footer())
        first_col = list(self.columns.values())[0]
        self.call_after_refresh(lambda: first_col.focus())

        if self.is_online and not config.is_local_only():
            self.background_full_sync()

    def reload_board_data(self) -> None:
        from backends import get_backend
        get_backend().clear_cache()
        for widget_id in ("#search-bar", "#board-container", "#cmd-bar"):
            try:
                self.query_one(widget_id).remove()
            except Exception:
                pass
        for cls in (Header, Footer):
            try:
                self.query(cls).first().remove()
            except Exception:
                pass
        self.call_after_refresh(self.load_board_data)

    def refresh_ui_from_local_db(self) -> None:
        self.tasks_data = db.get_all_local_tasks()
        wip_limits = config.get_wip_limits()

        SORT_LABELS = {"due": " ↕DUE", "priority": " ↕PRIO", "name": " ↕NAME", "default": ""}
        COLUMN_LABELS = {"Not started": "TODO", "In progress": "IN PROGRESS", "Done": "DONE"}

        for status, col in self.columns.items():
            if not col.is_mounted:
                continue
            col.remove_children()
            tasks = self._sort_tasks(self.tasks_data.get(status, []), self._col_sort.get(status, "default"))

            label = COLUMN_LABELS.get(status, status.upper())
            sort_label = SORT_LABELS.get(self._col_sort.get(status, "default"), "")
            wip = wip_limits.get(status, 0)
            wip_str = f"/{wip}" if wip else ""
            exceeded = wip and len(tasks) > wip

            col.border_title = f"{label} ({len(tasks)}{wip_str}){sort_label}{'  ⚠ WIP!' if exceeded else ''}"
            col.set_class(bool(exceeded), "wip-exceeded")

            if not tasks:
                col.mount(Static("No tasks here", classes="empty-col-msg"))
            else:
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
                        assignee=task.get("assignee"),
                        recurring_interval=task.get("recurring_interval"),
                    ))
                    # Restore selection highlight across re-renders
                    if task["id"] in self._selected:
                        col.query(TaskCard).last().add_class("selected")

    @work(thread=True)
    def background_full_sync(self) -> None:
        if not self.is_online or config.is_local_only():
            return

        known = set(self.columns.keys())
        backend = self._get_backend()

        def _syncing(): self._set_sync_status("Syncing...")
        self.call_from_thread(_syncing)

        success = backend.full_sync()

        if success:
            new_statuses = set(db.get_unique_statuses())
            if new_statuses - known:
                self.call_from_thread(self.reload_board_data)
            else:
                self.call_from_thread(self.refresh_ui_from_local_db)
            def _done(): self._set_sync_status("")
            self.call_from_thread(_done)
        else:
            def _err(): self._set_sync_status("Sync Error")
            self.call_from_thread(_err)

    # ── search / navigation ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.control.id != "search-bar":
            return
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
                    val = frag[4:]
                    if not card.due_date:
                        matches_all = False; break
                    try:
                        due = datetime.date.fromisoformat(card.due_date.split("T")[0])
                        if val == "today" and due != today: matches_all = False
                        elif val == "overdue" and due >= today: matches_all = False
                        elif val not in ("today", "overdue") and val not in card.due_date.lower(): matches_all = False
                    except Exception:
                        if val not in card.due_date.lower(): matches_all = False
                elif frag.startswith("assignee:"):
                    val = frag[9:]
                    if not (card.assignee and val in card.assignee.lower()): matches_all = False
                elif frag.startswith("priority:"):
                    val = frag[9:]
                    if not (card.priority and val in card.priority.lower()): matches_all = False
                else:
                    if frag not in card.title.lower() and not any(frag in t.lower() for t in card.tags):
                        matches_all = False
                if not matches_all: break
            card.set_class(not matches_all, "hidden")

    def action_escape_menus(self) -> None:
        # Clear bulk selection first
        if self._selected:
            self._selected.clear()
            for card in self.query(TaskCard):
                card.remove_class("selected")
            self._update_selection_subtitle()
            return
        for widget_id in ["#cmd-bar", "#search-bar"]:
            try:
                w = self.query_one(widget_id)
                w.remove_class("-visible")
                if widget_id == "#search-bar":
                    w.value = ""
                    for card in self.query(TaskCard): card.remove_class("hidden")
            except Exception:
                pass
        try:
            list(self.columns.values())[0].focus()
        except Exception:
            pass

    def action_open_search_bar(self) -> None:
        try:
            s = self.query_one("#search-bar")
            s.add_class("-visible")
            s.focus()
        except Exception:
            pass

    # ── bulk select ───────────────────────────────────────────────────────────

    def action_toggle_select(self) -> None:
        card = self.focused
        if not isinstance(card, TaskCard):
            return
        if card.toggle_selected():
            self._selected.add(card.task_id)
        else:
            self._selected.discard(card.task_id)
        self._update_selection_subtitle()

    def action_select_all(self) -> None:
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        if not isinstance(col, KanbanColumn):
            return
        for card in col.query(TaskCard):
            card.add_class("selected")
            self._selected.add(card.task_id)
        self._update_selection_subtitle()

    def _bulk_move(self, target_status: str) -> None:
        """Move all selected cards to target_status."""
        if not self._selected or target_status not in self.columns:
            return
        for task_id in list(self._selected):
            # Find the task dict
            for tasks in self.tasks_data.values():
                task = next((t for t in tasks if t["id"] == task_id), None)
                if task:
                    db.queue_update(task_id, task["name"], target_status, task["desc"],
                                    task.get("due_date"), task.get("priority"), task.get("assignee"))
                    break
        self._selected.clear()
        self.refresh_ui_from_local_db()
        self._update_selection_subtitle()
        if not config.is_local_only():
            self.background_full_sync()

    def _bulk_delete(self) -> None:
        """Archive all selected cards."""
        if not self._selected:
            return
        for task_id in list(self._selected):
            db.queue_delete(task_id)
        self._selected.clear()
        self.refresh_ui_from_local_db()
        self._update_selection_subtitle()
        if not config.is_local_only():
            self.background_full_sync()

    # ── sort ──────────────────────────────────────────────────────────────────

    def action_sort(self) -> None:
        focused = self.focused
        col = focused.parent if isinstance(focused, TaskCard) else focused
        status = next((s for s, c in self.columns.items() if c is col), None)
        if status is None:
            return
        modes = ["default", "due", "priority", "name"]
        current = self._col_sort.get(status, "default")
        self._col_sort[status] = modes[(modes.index(current) + 1) % len(modes)]
        self.notify(f"[{status}] Sort: {self._col_sort[status]}")
        self.refresh_ui_from_local_db()

    # ── quit ──────────────────────────────────────────────────────────────────

    def action_quit(self) -> None:
        pending = db.get_pending_tasks()
        if pending and not config.is_local_only():
            self.push_screen(PendingQuitScreen(len(pending)))
        else:
            self.exit()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def action_create_task(self, title: str, tags: list, desc: str,
                           due_date: str = None, priority: str = None,
                           assignee: str = None, recurring_interval: str = None) -> None:
        temp_id = f"local_{uuid.uuid4().hex}"
        first_status = list(self.columns.keys())[0] if self.columns else "Not started"
        db.queue_create(temp_id, title, first_status, tags, desc, due_date, priority, assignee, recurring_interval)
        self.refresh_ui_from_local_db()
        if not config.is_local_only():
            self.background_full_sync()

    def action_move_right(self) -> None:
        card = self.focused
        if not isinstance(card, TaskCard):
            return
        # If there are bulk-selected cards, bulk move them all to the next column
        if self._selected:
            statuses = list(self.columns.keys())
            if card.status in statuses:
                idx = statuses.index(card.status)
                if idx < len(statuses) - 1:
                    self._bulk_move(statuses[idx + 1])
            return
        statuses = list(self.columns.keys())
        if card.status in statuses:
            idx = statuses.index(card.status)
            if idx < len(statuses) - 1:
                new_status = statuses[idx + 1]
                self.undo_stack.append({
                    "type": "move", "task_id": card.task_id, "title": card.title,
                    "desc": card.description, "from": card.status, "to": new_status,
                    "due_date": card.due_date, "priority": card.priority,
                    "assignee": card.assignee, "tags": card.tags,
                })
                db.queue_update(card.task_id, card.title, new_status, card.description,
                                card.due_date, card.priority, card.assignee)
                self.refresh_ui_from_local_db()
                if not config.is_local_only():
                    self.background_full_sync()

    def action_move_left(self) -> None:
        card = self.focused
        if not isinstance(card, TaskCard):
            return
        if self._selected:
            statuses = list(self.columns.keys())
            if card.status in statuses:
                idx = statuses.index(card.status)
                if idx > 0:
                    self._bulk_move(statuses[idx - 1])
            return
        statuses = list(self.columns.keys())
        if card.status in statuses:
            idx = statuses.index(card.status)
            if idx > 0:
                new_status = statuses[idx - 1]
                self.undo_stack.append({
                    "type": "move", "task_id": card.task_id, "title": card.title,
                    "desc": card.description, "from": card.status, "to": new_status,
                    "due_date": card.due_date, "priority": card.priority,
                    "assignee": card.assignee, "tags": card.tags,
                })
                db.queue_update(card.task_id, card.title, new_status, card.description,
                                card.due_date, card.priority, card.assignee)
                self.refresh_ui_from_local_db()
                if not config.is_local_only():
                    self.background_full_sync()

    def action_undo(self) -> None:
        if not self.undo_stack:
            self.notify("Nothing to undo.", severity="warning")
            return
        action = self.undo_stack.pop()
        if action.get("type") == "delete":
            if action["task_id"].startswith("local_"):
                db.queue_create(action["task_id"], action["title"], action["status"],
                                action["tags"], action["desc"], action["due_date"],
                                action["priority"], action["assignee"])
            else:
                db.queue_update(action["task_id"], action["title"], action["status"],
                                action["desc"], action["due_date"], action["priority"],
                                action["assignee"])
            self.notify(f"Undo: Restored '{action['title']}'")
        else:
            db.queue_update(action["task_id"], action["title"], action["from"], action["desc"],
                            action.get("due_date"), action.get("priority"),
                            action.get("assignee"), action.get("tags"))
            self.notify(f"Undo: Moved back to {action['from']}")
        self.refresh_ui_from_local_db()

    def action_update_task_details(self, card, new_title, new_desc, new_tags: list = None,
                                   due_date: str = None, priority: str = None,
                                   assignee: str = None, recurring_interval: str = None) -> None:
        db.queue_update(card.task_id, new_title, card.status, new_desc,
                        due_date, priority, assignee, new_tags)
        db.update_recurring_interval(card.task_id, recurring_interval)
        self.refresh_ui_from_local_db()
        if not config.is_local_only():
            self.background_full_sync()

    def action_delete_task(self) -> None:
        if self._selected:
            self.push_screen(ConfirmBulkDeleteScreen(len(self._selected)))
            return
        card = self.focused
        if isinstance(card, TaskCard):
            self.push_screen(ConfirmDeleteScreen(card))

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_confirm_delete(self, card: TaskCard) -> None:
        self.undo_stack.append({
            "type": "delete", "task_id": card.task_id, "title": card.title,
            "status": card.status, "desc": card.description, "tags": card.tags,
            "due_date": card.due_date, "priority": card.priority, "assignee": card.assignee,
        })
        db.queue_delete(card.task_id)
        self.refresh_ui_from_local_db()
        if not config.is_local_only():
            self.background_full_sync()

    def action_push_new_task(self) -> None:
        self.push_screen(NewTaskScreen())

    def action_open_task_details(self) -> None:
        if isinstance(self.focused, TaskCard):
            self.push_screen(TaskDetailScreen(self.focused))

    def action_open_command_bar(self) -> None:
        """Open the command palette (: key)."""
        self.push_screen(CommandPaletteScreen())

    def _show_command_bar(self, prefill: str = ":") -> None:
        """Open the raw command bar pre-filled with a command prefix (used by palette)."""
        try:
            c = self.query_one("#cmd-bar")
            c.add_class("-visible")
            c.value = prefill
            c.focus()
            c.cursor_position = len(prefill)
        except Exception:
            pass

    def action_refresh(self) -> None:
        if config.is_local_only():
            self.notify("Local-only mode — no sync.", severity="warning")
        elif self.is_online:
            self.background_full_sync()
        else:
            self.notify("Offline — can't sync.", severity="warning")

    # ── command bar ───────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.control.id != "cmd-bar":
            return
        cmd = event.value.strip()
        self.action_escape_menus()
        try:
            self._handle_command(cmd)
        except Exception as e:
            self.notify(f"Command Error: {e}", severity="error")

    def _handle_command(self, cmd: str) -> None:
        if cmd.startswith(":new "):
            content = cmd[5:]
            tags = re.findall(r'#(\w+)', content)
            due_m = re.search(r'\bdue:(\S+)', content)
            prio_m = re.search(r'\bpriority:(\w+)', content, re.IGNORECASE)
            recur_m = re.search(r'\brecurring:(\w+)', content, re.IGNORECASE)
            due = due_m.group(1) if due_m else None
            prio = prio_m.group(1).capitalize() if prio_m else None
            recurring = recur_m.group(1).lower() if recur_m else None
            title = re.sub(r'#\w+', '', content)
            title = re.sub(r'\bdue:\S+', '', title)
            title = re.sub(r'\bpriority:\w+', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\brecurring:\w+', '', title, flags=re.IGNORECASE)
            title = title.strip()
            if title:
                self.action_create_task(title, tags, "", due, prio, None, recurring)

        elif cmd in (":q", ":quit"):
            self.action_quit()

        elif cmd in (":refresh", ":r"):
            self.background_full_sync()

        elif cmd in (":rm", ":del"):
            self.action_delete_task()

        elif cmd == ":config":
            self.push_screen(SetupScreen())

        elif cmd == ":backend":
            self.push_screen(BackendScreen())

        elif cmd == ":stats":
            self.push_screen(StatsScreen())

        elif cmd == ":wip":
            self.push_screen(WipScreen(list(self.columns.keys())))

        elif cmd == ":theme-reset":
            import theme
            theme.write_defaults()
            self.notify("Default theme.json written to ~/.config/tuido/theme.json — restart to apply.")

        elif cmd.startswith(":wip "):
            # :wip <column> <limit>  e.g.  :wip In progress 3
            parts = cmd[5:].rsplit(" ", 1)
            if len(parts) == 2:
                col_name, limit_str = parts
                col_name = col_name.strip()
                try:
                    limit = int(limit_str.strip())
                    config.set_wip_limit(col_name, limit)
                    self.notify(f"WIP limit for '{col_name}' set to {limit}")
                    self.refresh_ui_from_local_db()
                except ValueError:
                    self.notify("Usage: :wip <column name> <number>", severity="error")

        elif cmd.startswith(":json-path "):
            path = cmd[11:].strip()
            config.set_json_sync_path(path)
            self.notify(f"JSON sync path set to: {path}")

        elif cmd.startswith(":switch "):
            target = cmd[8:].strip()
            if config.switch_board(target):
                self.notify(f"Switched to board: {target}")
                self.reload_board_data()
            else:
                self.notify("Invalid board alias.", severity="error")

        elif cmd.startswith(":export"):
            parts = cmd.split(" ", 1)
            filename = parts[1].strip() if len(parts) > 1 else "export.md"
            self.action_export_markdown(filename)

        elif cmd.startswith(":move "):
            # :move <status>  — bulk move selected cards
            target = cmd[6:].strip()
            if self._selected:
                self._bulk_move(target)
            else:
                self.notify("No cards selected. Use Space to select.", severity="warning")

        elif cmd == ":help":
            self.action_help()

        elif cmd == ":boards":
            boards = config.get_all_boards()
            current = config.get_current_board()
            msg = "[bold cyan]Saved Boards:[/]\n"
            for alias, db_id in boards.items():
                mark = "[bold green]▶[/] " if alias == current else "  "
                msg += f"{mark}[white]{alias}[/] (ID: {db_id[:8]}...)\n"
            msg += "\nUse [italic]:switch <alias>[/] to swap."
            self.notify(msg, title="Your Boards", timeout=8)

        else:
            self.notify(f"Unknown command: {cmd}", severity="error")

    def action_export_markdown(self, filename: str) -> None:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("# TUI-do Export\n\n")
                for status in list(self.columns.keys()):
                    tasks = self.tasks_data.get(status, [])
                    if not tasks:
                        continue
                    f.write(f"## {status.upper()}\n\n")
                    for t in tasks:
                        f.write(f"- {'[x]' if status == 'Done' else '[ ]'} **{t['name']}**")
                        if t.get("assignee"):
                            f.write(f" (@{t['assignee']})")
                        if t.get("recurring_interval"):
                            f.write(f" ↻{t['recurring_interval']}")
                        f.write("\n")
            self.notify(f"Exported to {filename}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    # ── focus navigation ──────────────────────────────────────────────────────

    def action_focus_down(self) -> None:
        if isinstance(self.focused, TaskCard):
            sibs = [s for s in self.focused.parent.query(TaskCard) if not s.has_class("hidden")]
            if self.focused in sibs:
                idx = sibs.index(self.focused)
                if idx < len(sibs) - 1:
                    sibs[idx + 1].focus()

    def action_focus_up(self) -> None:
        if isinstance(self.focused, TaskCard):
            sibs = [s for s in self.focused.parent.query(TaskCard) if not s.has_class("hidden")]
            if self.focused in sibs:
                idx = sibs.index(self.focused)
                if idx > 0:
                    sibs[idx - 1].focus()

    def action_focus_left(self) -> None:
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        cols = list(self.query(KanbanColumn))
        if col not in cols:
            return
        idx = cols.index(col)
        if idx > 0:
            cards = [c for c in cols[idx - 1].query(TaskCard) if not c.has_class("hidden")]
            (cards[0] if cards else cols[idx - 1]).focus()

    def action_focus_right(self) -> None:
        col = self.focused.parent if isinstance(self.focused, TaskCard) else self.focused
        cols = list(self.query(KanbanColumn))
        if col not in cols:
            return
        idx = cols.index(col)
        if idx < len(cols) - 1:
            cards = [c for c in cols[idx + 1].query(TaskCard) if not c.has_class("hidden")]
            (cards[0] if cards else cols[idx + 1]).focus()
