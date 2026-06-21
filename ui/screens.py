from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Button, Static, TextArea, Select
from textual.containers import Vertical, VerticalScroll, Center, Middle, Horizontal
from textual import work


class SetupScreen(Screen):
    """Initial configuration screen for Notion Token and Database URL."""

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("TUI-do Setup", classes="dialog-title")
                    yield Static("Notion Integration Secret:", classes="dialog-label")
                    yield Input(placeholder="ntn_...", id="token-input", password=True)
                    yield Static("Notion Database URL:", classes="dialog-label")
                    yield Input(placeholder="https://www.notion.so/...", id="db-input")
                    yield Button("Authenticate Workspace", variant="primary", id="setup-run")
                    yield Static("─── or ───", classes="dialog-label")
                    yield Button("Use Locally (No Notion)", variant="default", id="setup-local")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-run":
            self._submit()
        elif event.button.id == "setup-local":
            self._use_local()

    def _submit(self) -> None:
        token = self.query_one("#token-input", Input).value.strip()
        db_url = self.query_one("#db-input", Input).value.strip()
        if token and db_url:
            import config
            try:
                config.set_token(token)
                db_id = config.extract_database_id(db_url)
                config.save_board("default", db_id)
                config.set_current_board("default")
                self.app.reload_board_data()
                self.app.pop_screen()
            except ValueError as e:
                self.app.notify(str(e), severity="error")

    def _use_local(self) -> None:
        import config
        config.set_local_only()
        self.app.reload_board_data()
        self.app.pop_screen()


class NewTaskScreen(Screen):
    """Modal dialog for creating a new task with metadata."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    RECURRENCE_OPTIONS = [
        ("Daily", "daily"),
        ("Weekly", "weekly"),
        ("Monthly", "monthly"),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with VerticalScroll(classes="dialog-box"):
                yield Static("Create New Task", classes="dialog-title")

                yield Static("Title *", classes="dialog-label")
                yield Input(placeholder="Task name...", id="task-title")

                yield Static("Tags (space separated)", classes="dialog-label")
                yield Input(placeholder="feature bug urgent", id="task-tags")

                yield Static("Due Date (YYYY-MM-DD)", classes="dialog-label")
                yield Input(placeholder="2026-12-31", id="task-due")

                yield Static("Priority", classes="dialog-label")
                yield Input(placeholder="High / Medium / Low", id="task-priority")

                yield Static("Assignee", classes="dialog-label")
                yield Input(placeholder="Name", id="task-assignee")

                yield Static("Recurring", classes="dialog-label")
                yield Select(
                    self.RECURRENCE_OPTIONS,
                    id="task-recurring",
                    prompt="None (no recurrence)",
                )

                yield Static("Description", classes="dialog-label")
                yield TextArea(id="task-desc")

                yield Button("Create Task", variant="primary", id="create-btn")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-btn":
            self._submit()

    def _submit(self) -> None:
        title = self.query_one("#task-title", Input).value.strip()
        if not title:
            self.app.notify("Title is required.", severity="warning")
            return
        tags_str = self.query_one("#task-tags", Input).value.strip()
        due = self.query_one("#task-due", Input).value.strip() or None
        prio = self.query_one("#task-priority", Input).value.strip() or None
        assignee = self.query_one("#task-assignee", Input).value.strip() or None
        desc = self.query_one("#task-desc", TextArea).text
        tags_list = tags_str.split() if tags_str else []
        sel_val = self.query_one("#task-recurring", Select).value
        recurring = None if sel_val is Select.BLANK else sel_val
        self.app.action_create_task(title, tags_list, desc, due, prio, assignee, recurring)
        self.app.pop_screen()


class TaskDetailScreen(Screen):
    """View and edit all task fields, with Notion subtasks/comments when synced."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    RECURRENCE_OPTIONS = [
        ("Daily", "daily"),
        ("Weekly", "weekly"),
        ("Monthly", "monthly"),
    ]

    def __init__(self, task_card, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_card = task_card

    def compose(self) -> ComposeResult:
        ri = self.task_card.recurring_interval
        with Center():
            with VerticalScroll(classes="dialog-box large-dialog"):
                yield Static(f"Edit Task [dim]({self.task_card.sync_status})[/]", classes="dialog-title")

                yield Static("Title", classes="dialog-label")
                yield Input(value=self.task_card.title, id="dt-title")

                yield Static("Due Date (YYYY-MM-DD)", classes="dialog-label")
                yield Input(value=self.task_card.due_date or "", placeholder="2026-12-31", id="dt-due")

                yield Static("Priority", classes="dialog-label")
                yield Input(value=self.task_card.priority or "", placeholder="High / Medium / Low", id="dt-priority")

                yield Static("Assignee", classes="dialog-label")
                yield Input(value=self.task_card.assignee or "", placeholder="Name", id="dt-assignee")

                yield Static("Recurring", classes="dialog-label")
                yield Select(
                    self.RECURRENCE_OPTIONS,
                    id="dt-recurring",
                    value=ri if ri else Select.BLANK,
                    prompt="None (no recurrence)",
                )

                yield Static("Tags (space separated)", classes="dialog-label")
                yield Input(value=" ".join(self.task_card.tags), id="dt-tags")

                yield Static("Description", classes="dialog-label")
                yield TextArea(text=self.task_card.description or "", id="dt-desc")

                yield Static("Loading Notion data...", id="dt-loading", classes="dialog-label")
                yield Vertical(id="dt-subtasks-container", classes="hidden")
                yield Vertical(id="dt-comments-container", classes="hidden")

                yield Button("Save Changes", id="dt-save", variant="primary")

    def on_mount(self) -> None:
        import config as cfg
        # Only hit the Notion API when we're actually in Notion mode and the task is synced
        if not cfg.is_local_only() and self.task_card.sync_status == "synced":
            self.load_context()
        else:
            self.call_after_refresh(self._hide_cloud_section)

    def _hide_cloud_section(self) -> None:
        try:
            self.query_one("#dt-loading").add_class("hidden")
        except Exception:
            pass

    @work(thread=True)
    def load_context(self) -> None:
        import api
        import config as cfg
        try:
            if self.task_card.sync_status == "synced" and not cfg.is_local_only():
                subtasks = api.get_subtasks(self.task_card.task_id)
                comments = api.get_comments(self.task_card.task_id)
            else:
                subtasks, comments = [], []
            self.app.call_from_thread(self._render_context, subtasks, comments)
        except Exception:
            self.app.call_from_thread(self._render_context, [], [])

    def _render_context(self, subtasks, comments):
        try:
            self.query_one("#dt-loading").add_class("hidden")
            if subtasks:
                c = self.query_one("#dt-subtasks-container")
                c.remove_children()
                c.remove_class("hidden")
                c.mount(Static("── Subtasks ──", classes="dialog-label"))
                for st in subtasks:
                    mark = "[bold green]✔[/][strike]" if st["checked"] else "[white]☐[/]"
                    end = "[/strike]" if st["checked"] else ""
                    c.mount(Static(f"  {mark} {st['text']}{end}", classes="dt-context-item"))
            if comments:
                c = self.query_one("#dt-comments-container")
                c.remove_children()
                c.remove_class("hidden")
                c.mount(Static("── Comments ──", classes="dialog-label"))
                for cm in comments:
                    c.mount(Static(f"  [bold blue]{cm['author']}[/]: {cm['text']}", classes="dt-context-item"))
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dt-save":
            self._save()

    def _save(self) -> None:
        new_title = self.query_one("#dt-title", Input).value.strip()
        if not new_title:
            self.app.notify("Title cannot be empty.", severity="warning")
            return
        new_due = self.query_one("#dt-due", Input).value.strip() or None
        new_prio = self.query_one("#dt-priority", Input).value.strip() or None
        new_assignee = self.query_one("#dt-assignee", Input).value.strip() or None
        sel_val = self.query_one("#dt-recurring", Select).value
        new_recurring = None if sel_val is Select.BLANK else sel_val
        new_tags_str = self.query_one("#dt-tags", Input).value.strip()
        new_tags = new_tags_str.split() if new_tags_str else []
        new_desc = self.query_one("#dt-desc", TextArea).text.strip()
        self.app.action_update_task_details(
            self.task_card, new_title, new_desc, new_tags,
            new_due, new_prio, new_assignee, new_recurring,
        )
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
                    yield Static("Press [bold]y[/] to confirm or [bold]Escape[/] to cancel.", classes="dialog-label")
                    yield Button("Archive Task", id="del-confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "del-confirm":
            self.action_confirm()

    def action_confirm(self) -> None:
        self.app.action_confirm_delete(self.task_card)
        self.app.pop_screen()


class HelpScreen(Screen):
    """Help modal explaining keys and commands."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with VerticalScroll(classes="dialog-box large-dialog"):
                yield Static("TUI-do Kanban Quick Help", classes="dialog-title")
                yield Static("[bold cyan]Navigation & Actions[/]")
                yield Static("  [white]h/j/k/l / Arrows[/]  — Navigate board")
                yield Static("  [white]Enter[/]             — Edit task / view subtasks")
                yield Static("  [white][ / ][/]             — Move task left / right")
                yield Static("  [white]n[/]                 — New task dialog")
                yield Static("  [white]x[/]                 — Archive focused task")
                yield Static("  [white]u[/]                 — Undo last action")
                yield Static("  [white]s[/]                 — Cycle sort on focused column\n")
                yield Static("[bold cyan]Search & Commands[/]")
                yield Static("  [white]/[/]                 — Filter by title, #tag, due:today…")
                yield Static("  [white]:new <title>[/]      — Quick-create (supports due:DATE priority:High)")
                yield Static("  [white]:stats[/]            — Board statistics")
                yield Static("  [white]:switch <alias>[/]   — Swap to a different board")
                yield Static("  [white]:export <file>[/]    — Save board to Markdown")
                yield Static("  [white]:config[/]           — Change Notion token/ID\n")
                yield Static("[bold cyan]App Control[/]")
                yield Static("[bold cyan]Bulk Operations[/]")
                yield Static("  [white]Space[/]             — Toggle select card")
                yield Static("  [white]Ctrl+A[/]            — Select all in column")
                yield Static("  [white][ / ] with selection[/] — Bulk move left / right")
                yield Static("  [white]x with selection[/]  — Bulk archive")
                yield Static("  [white]:move <column>[/]    — Bulk move to named column\n")
                yield Static("[bold cyan]App Control[/]")
                yield Static("  [white]r[/]                 — Refresh / full sync")
                yield Static("  [white]d[/]                 — Toggle dark/light mode")
                yield Static("  [white]q[/]                 — Quit (warns if tasks are unsynced)")
                yield Static("  [white]:wip[/]              — Set WIP limits per column")
                yield Static("  [white]:backend[/]          — Switch sync backend (Notion/JSON/Local)")
                yield Static("  [white]:json-path <path>[/] — Set JSON sync file location")
                yield Static("  [white]:theme-reset[/]      — Write a default theme.json\n")
                yield Static("Press [bold red]Escape[/] to close.", classes="dialog-label")
                yield Button("Close", variant="success", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.app.pop_screen()


class PendingQuitScreen(Screen):
    """Warns the user when there are unsynced tasks before quitting."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
        ("y", "confirm_quit", "Quit Anyway"),
    ]

    def __init__(self, count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = count

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Unsaved Changes", classes="dialog-title")
                    yield Static(
                        f"[bold yellow]{self.count} task(s)[/] are queued to sync with Notion.",
                        classes="dialog-label"
                    )
                    yield Static(
                        "Press [bold]y[/] to quit anyway, or [bold]Escape[/] to go back.",
                        classes="dialog-label"
                    )
                    yield Button("Cancel", variant="default", id="pq-cancel")
                    yield Button("Quit Anyway", variant="error", id="pq-quit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pq-quit":
            self.action_confirm_quit()
        elif event.button.id == "pq-cancel":
            self.app.pop_screen()

    def action_confirm_quit(self) -> None:
        self.app.exit()


class StatsScreen(Screen):
    """Modal showing board statistics."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        import db
        stats = db.get_stats()
        done_pct = f"{int(stats['done'] / stats['total'] * 100)}%" if stats["total"] else "0%"
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Board Stats", classes="dialog-title")
                    yield Static(f"Total tasks:   [bold white]{stats['total']}[/]", classes="dialog-label")
                    yield Static(f"Done:          [bold green]{stats['done']}[/] ({done_pct})", classes="dialog-label")
                    yield Static(f"Overdue:       [bold red]{stats['overdue']}[/]", classes="dialog-label")
                    yield Static(f"Pending sync:  [bold yellow]{stats['pending_sync']}[/]", classes="dialog-label")
                    yield Button("Close", variant="success", id="stats-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stats-close":
            self.app.pop_screen()


class ConfirmBulkDeleteScreen(Screen):
    """Confirm before bulk-archiving selected cards."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
        ("y", "confirm", "Yes, Archive All"),
    ]

    def __init__(self, count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = count

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Bulk Archive?", classes="dialog-title")
                    yield Static(
                        f"Archive [bold yellow]{self.count} selected task(s)[/]?",
                        classes="dialog-label",
                    )
                    yield Static(
                        "Press [bold]y[/] to confirm or [bold]Escape[/] to cancel.",
                        classes="dialog-label",
                    )
                    yield Button("Archive All", variant="error", id="bulk-del-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bulk-del-confirm":
            self.action_confirm()

    def action_confirm(self) -> None:
        self.app._bulk_delete()
        self.app.pop_screen()


class WipScreen(Screen):
    """Set or clear a WIP (Work In Progress) limit for a column."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    def __init__(self, columns: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._columns = columns

    def compose(self) -> ComposeResult:
        import config
        limits = config.get_wip_limits()
        with Center():
            with Middle():
                with VerticalScroll(classes="dialog-box"):
                    yield Static("WIP Limits", classes="dialog-title")
                    yield Static(
                        "Set the max number of tasks allowed per column.\n"
                        "0 = no limit.",
                        classes="dialog-label",
                    )
                    for col in self._columns:
                        current = limits.get(col, 0)
                        yield Static(col, classes="dialog-label")
                        yield Input(
                            value=str(current),
                            placeholder="0 = unlimited",
                            id=f"wip-{col.replace(' ', '_')}",
                        )
                    yield Button("Save", variant="primary", id="wip-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wip-save":
            import config
            for col in self._columns:
                field_id = f"#wip-{col.replace(' ', '_')}"
                try:
                    val = int(self.query_one(field_id, Input).value.strip() or "0")
                    config.set_wip_limit(col, val)
                except ValueError:
                    pass
            self.app.notify("WIP limits saved.")
            self.app.refresh_ui_from_local_db()
            self.app.pop_screen()


class BackendScreen(Screen):
    """Choose the sync backend: Notion, JSON file, or Local-only."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    def compose(self) -> ComposeResult:
        import config
        current = config.get_backend_type()
        with Center():
            with Middle():
                with Vertical(classes="dialog-box"):
                    yield Static("Sync Backend", classes="dialog-title")
                    yield Static(
                        f"Current: [bold]{current}[/]",
                        classes="dialog-label",
                    )
                    yield Button("Notion (cloud sync)", variant="primary", id="be-notion")
                    yield Button("JSON File (shared folder)", variant="default", id="be-json")
                    yield Button("Local Only (no sync)", variant="default", id="be-local")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        import config
        if event.button.id == "be-notion":
            config.set_backend_type("notion")
            self.app.pop_screen()
            self.app.push_screen(SetupScreen())
        elif event.button.id == "be-json":
            config.set_backend_type("json")
            self.app.notify(
                f"JSON backend active. Sync file: {config.get_json_sync_path()}\n"
                "Override with  :json-path /your/path/tuido.json",
                timeout=8,
            )
            self.app.pop_screen()
        elif event.button.id == "be-local":
            config.set_local_only()
            self.app.notify("Local-only mode enabled. No sync will occur.")
            self.app.pop_screen()


class CommandPaletteScreen(Screen):
    """Searchable menu of all : commands. Press Enter to run; click to pre-fill."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    COMMANDS = [
        (":new <title>",      "Create a task  (#tag  due:DATE  priority:High  recurring:weekly)"),
        (":stats",            "Board statistics: total, done %, overdue, pending sync"),
        (":wip",              "Open WIP limit editor for all columns"),
        (":wip <col> <n>",    "Set a column WIP limit inline  e.g.  :wip In progress 3"),
        (":backend",          "Switch sync backend: Notion / JSON file / Local-only"),
        (":json-path <path>", "Set the JSON sync file path"),
        (":move <column>",    "Bulk-move selected cards to a named column"),
        (":switch <alias>",   "Switch to a saved board"),
        (":boards",           "List all saved boards"),
        (":config",           "Update Notion token / database URL"),
        (":export <file.md>", "Export the board to a Markdown file"),
        (":theme-reset",      "Write default theme.json to ~/.config/tuido/"),
        (":refresh",          "Force a full sync now"),
        (":help",             "Open keyboard shortcut help"),
        (":quit",             "Quit TUI-do"),
    ]

    # These commands need no arguments — run immediately when clicked
    _INSTANT = {":stats", ":wip", ":backend", ":boards", ":config",
                ":theme-reset", ":refresh", ":help", ":quit"}

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(classes="dialog-box large-dialog"):
                    yield Static("Command Palette", classes="dialog-title")
                    yield Input(placeholder="Filter or type a command...", id="palette-input")
                    yield VerticalScroll(id="palette-list")
                    yield Static(
                        "[dim]Enter[/dim] run · [dim]Click[/dim] pre-fill · [dim]Esc[/dim] cancel",
                        classes="dialog-label",
                    )

    def on_mount(self) -> None:
        self._build_list("")
        self.query_one("#palette-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._build_list(event.value.lower().lstrip(":"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        if raw:
            self.app.pop_screen()
            self.app._handle_command(":" + raw.lstrip(":"))

    def _build_list(self, query: str) -> None:
        container = self.query_one("#palette-list", VerticalScroll)
        container.remove_children()
        for i, (cmd, desc) in enumerate(self.COMMANDS):
            if not query or query in cmd or query in desc.lower():
                container.mount(
                    Button(f"{cmd}   [dim]{desc}[/dim]", id=f"pcmd_{i}", classes="palette-cmd-btn")
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not (event.button.id or "").startswith("pcmd_"):
            return
        idx = int(event.button.id.split("_", 1)[1])
        cmd_str = self.COMMANDS[idx][0]
        base_cmd = cmd_str.split()[0]
        self.app.pop_screen()
        if base_cmd in self._INSTANT:
            self.app._handle_command(base_cmd)
        else:
            # Pre-fill the raw command bar so user can supply args
            prefix = base_cmd + " "
            self.app._show_command_bar(prefix)
