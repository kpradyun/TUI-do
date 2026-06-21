# TUI-do

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-8A2BE2)](https://textual.textualize.io/)
[![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)](#testing)

A keyboard-driven Kanban board for the terminal. Works fully offline with SQLite — optionally syncs to Notion, a shared JSON file, or runs completely local. Built with [Textual](https://textual.textualize.io/).

> Developed as part of an Integrated M.Tech CSE project at the University of Hyderabad.

---

## Features

**Board**
- Three-column Kanban (Todo → In Progress → Done) with dynamic columns pulled from your Notion schema
- WIP (Work In Progress) limits per column — column border turns red when exceeded
- Overdue cards highlighted with a red left border
- Done-column task titles shown with dim strikethrough
- Empty column placeholder so the board never looks broken
- Sort any column by due date, priority, or name (`s` key cycles modes)

**Tasks**
- Full task metadata: title, description, tags, due date, priority, assignee
- Edit every field after creation — press `Enter` on any card to open the detail screen
- Recurring tasks (daily / weekly / monthly) — completed recurring tasks auto-spawn a fresh copy on the next due date; the card shows a `↻D / ↻W / ↻M` badge
- Bulk select with `Space`, select all with `Ctrl+A`, then bulk move or bulk archive in one keystroke

**Sync**
- Offline-first: all reads and writes go to SQLite immediately, sync happens in the background
- Three sync backends: Notion, shared JSON file (Dropbox / OneDrive friendly), or local-only
- Notion sync handles pagination (databases with more than 100 tasks), rate-limit back-off (`Retry-After`), and full tag sync on both creates and updates
- 60-second background heartbeat; auto-syncs on reconnect after going offline
- Quit guard — warns you if unsynced tasks would be lost

**UX**
- Vim-style navigation (`h j k l` or arrow keys)
- Visual command palette (press `:`) — searchable list of all commands; type to filter, click to run or pre-fill
- Smart multi-criteria search: `due:today #feature priority:high assignee:pradyun`
- Undo last move or delete (`u`)
- Markdown export (`:export`)
- Desktop notifications on startup for overdue / due-today tasks
- Custom color theme via `~/.config/tuido/theme.json`

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Textual TUI  (ui/)                   │
│  Board · Command Palette · Search · Bulk Select · WIP  │
└───────────────────────┬────────────────────────────────┘
                        │ instant read/write
┌───────────────────────▼────────────────────────────────┐
│              SQLite Local Cache  (db.py)               │
│     tasks · offline queue · board index · stats        │
└───────────────────────┬────────────────────────────────┘
                        │ background thread (60 s)
┌───────────────────────▼────────────────────────────────┐
│              Sync Backend  (backends/)                 │
│                                                        │
│   NotionBackend   JSONBackend   NullBackend            │
│   (notion_client) (shared file) (local-only)           │
└────────────────────────────────────────────────────────┘
```

The UI never waits for the network. Every action writes to SQLite first; the backend worker picks up the queue on its next cycle or when you press `r`.

---

## Installation

### Option A — install as a CLI command (recommended)

```bash
git clone https://github.com/kpradyun/TUI-do.git
cd TUI-do

python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

pip install .
tuido
```

### Option B — run directly

```bash
pip install -r requirements.txt
python main.py
```

### Windows shortcut

Double-click `tuido.bat` from the project folder — it activates the venv and launches automatically.

---

## First Run

On first launch you will see the setup screen with three options:

1. **Authenticate with Notion** — enter your Integration Token and database URL. Credentials are stored in `~/.config/tuido/config.json` with `0o600` permissions, never in the project directory.
2. **JSON file sync** — point to a file on a shared drive (Dropbox, OneDrive, etc.) for lightweight multi-machine sync without a Notion account.
3. **Use Locally** — skip sync entirely. Pure offline Kanban backed by SQLite.

You can switch backends at any time with `:backend`. For Notion setup (creating the integration, sharing the database, required schema) see **[SETUP.md](SETUP.md)**.

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `h j k l` / arrows | Navigate board |
| `n` | New task dialog |
| `Enter` | Edit task — opens detail screen with all fields editable |
| `[ ]` | Move task left / right |
| `s` | Cycle sort on focused column (due → priority → name → default) |
| `Space` | Toggle select card for bulk operation |
| `Ctrl+A` | Select all cards in focused column |
| `u` | Undo last action |
| `x` | Archive focused task (or bulk archive if cards are selected) |
| `r` | Refresh / full sync |
| `/` | Search and filter |
| `?` | Help |
| `:` | Command palette |
| `d` | Toggle dark / light mode |
| `q` | Quit (warns if unsynced tasks exist) |

---

## Command Palette

Press `:` to open a searchable command menu. Type to filter the list, press `Enter` to run what you typed, or click any command to run it immediately (for commands that need no arguments) or pre-fill the command bar (for commands that take arguments).

| Command | Action |
|---|---|
| `:new <title> [#tag] [due:DATE] [priority:High] [recurring:weekly]` | Create task inline |
| `:stats` | Board statistics (total, done %, overdue, pending sync) |
| `:wip` | Open WIP limit editor |
| `:wip <column> <n>` | Set WIP limit directly — e.g. `:wip In progress 3` |
| `:move <column>` | Bulk move selected cards to named column |
| `:backend` | Switch sync backend (Notion / JSON / Local) |
| `:json-path <path>` | Set the JSON sync file location |
| `:switch <alias>` | Switch to a different saved board |
| `:boards` | List all saved boards |
| `:config` | Update Notion token / database URL |
| `:export <file.md>` | Export board to Markdown |
| `:theme-reset` | Write a default `theme.json` to edit |
| `:refresh` / `:r` | Force sync now |
| `:rm` / `:del` | Archive focused task |
| `:help` | Help modal |
| `:q` / `:quit` | Quit |

---

## Search Syntax

Press `/` and type any combination of these:

| Syntax | Matches |
|---|---|
| `login` | Title contains "login" |
| `#bug` | Tasks tagged `bug` |
| `due:today` | Tasks due today |
| `due:overdue` | Past-due tasks |
| `priority:high` | High-priority tasks |
| `assignee:pradyun` | Tasks assigned to Pradyun |

Combine freely: `due:overdue #auth priority:high`

---

## WIP Limits

WIP (Work In Progress) limits cap how many tasks can be in a column at once — a core Lean/Kanban principle that prevents bottlenecks.

```
:wip In progress 3
```

When the limit is exceeded, the column border turns red and the header shows `⚠ WIP!`. Tasks can still be moved in (soft limit), which is intentional — the warning is informational.

To open a full editor for all columns at once: `:wip`

---

## Recurring Tasks

Create a task with a recurrence interval from the New Task dialog (select from the Recurring dropdown), or inline:

```
:new Weekly standup prep recurring:weekly due:2026-06-23
```

When a recurring task is moved to Done, TUI-do spawns a fresh copy at the next due date automatically on the next app launch. The card shows a badge: `↻D` (daily), `↻W` (weekly), `↻M` (monthly).

The recurring interval is local-only metadata — Notion has no native recurrence concept, so the interval is never pushed to or overwritten by Notion sync. You can edit or clear the interval at any time from the task detail screen.

---

## Task Detail Screen

Press `Enter` on any card to open the full edit screen. Every field is editable:

| Field | Notes |
|---|---|
| Title | Required |
| Due Date | `YYYY-MM-DD` format |
| Priority | `High`, `Medium`, or `Low` |
| Assignee | Free-text name |
| Recurring | Dropdown: None / Daily / Weekly / Monthly |
| Tags | Space-separated list |
| Description | Free-form text area |

Press `Enter` in any input field or click **Save Changes** to commit. Changes go to SQLite instantly and are synced on the next background cycle.

When using Notion sync and the task is already synced, the bottom of the screen also loads the task's Notion subtasks and comments (read-only).

---

## Sync Backends

Switch backends at any time with `:backend`.

| Backend | Best for |
|---|---|
| **Notion** | Full-featured cloud sync with comments, subtasks, and workspace collaboration |
| **JSON file** | Lightweight sync via Dropbox / OneDrive / NFS without a Notion account |
| **Local only** | Zero-dependency offline Kanban — no account needed |

### Notion sync behaviour

- Pulls all tasks from your Notion database (paginated — works beyond 100 tasks)
- Pushes locally-queued creates, updates (including tags), and deletes
- Respects Notion's `Retry-After` header on rate-limit responses (HTTP 429) with up to 4 automatic retries
- Custom Notion status options become extra Kanban columns in TUI-do
- Local-only fields (recurring interval, WIP limits) are never pushed to or overwritten by Notion

### JSON backend

The JSON backend writes a human-readable `tuido_sync.json`. Writes are atomic (written to a temp file then renamed) so a crash never corrupts the file.

```
:json-path /path/to/Dropbox/tuido_sync.json
```

---

## Theming

On first run, TUI-do writes `~/.config/tuido/theme.json` with the default palette. Edit it and restart to apply:

```json
{
  "accent":  "#f0c040",
  "success": "#00cc66",
  "error":   "#ff4444",
  "warning": "#ff8800",
  "primary": "#7b8cde"
}
```

Reset to defaults: `:theme-reset`

For deeper customization, edit `ui/app.tcss` directly.

---

## Testing

```bash
pip install pytest
pytest tests/ -v
```

35 tests covering all database operations and configuration functions with fully isolated temp directories — no real config or database is touched. Includes tests for recurring task logic, the recurring-interval cloud-pull preservation fix, `hard_delete`, and all CRUD operations.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Invalid token" on first run | Token must start with `secret_` or `ntn_` |
| Board shows empty after Notion setup | Confirm the database is shared with your Notion integration |
| Only 3 columns showing after Notion sync | Custom status columns appear after the first successful pull — press `r` to force one |
| Tasks not syncing | Press `r` to force sync; check internet connection |
| Sync Error in subtitle | Notion API may have returned an error — the app retries automatically on rate limits; check your token if it persists |
| Recurring tasks not resetting | The app processes recurring tasks on launch — open the app on or after the task's next due date |
| Recurring interval disappeared after sync | This was a known bug, now fixed — update to the latest version |
| Config reset needed | Delete `~/.config/tuido/config.json` and re-run |
| Switch to local-only | `:backend` → "Local Only (no sync)" |
| JSON sync file corrupted | Restore from `tuido_sync.json.tmp` if present (left by a crash mid-write) |
| Desktop notification not appearing | `plyer` is required — `pip install plyer`; on Linux you may also need `libnotify` |

---

## Project Structure

```
TUI-do/
├── main.py              # Entry point — startup tasks, theme injection, launch
├── config.py            # Credential and settings management (~/.config/tuido/)
├── db.py                # SQLite layer — offline queue, stats, recurring tasks
├── api.py               # Notion API — paginated pull, retry-aware push, schema
├── notifications.py     # Desktop notifications for due / overdue tasks
├── theme.py             # Color theme loader from theme.json
├── backends/
│   ├── base.py          # Abstract SyncBackend interface (ABC)
│   ├── notion_backend.py
│   └── json_backend.py  # Atomic writes — crash-safe
├── ui/
│   ├── app.py           # Main Textual app, all keybindings and actions
│   ├── app.tcss         # Stylesheet
│   ├── widgets.py       # TaskCard, KanbanColumn, CommandBar, SearchBar
│   └── screens.py       # All modal screens (setup, new task, edit, stats, palette, …)
├── tests/
│   ├── test_db.py       # 20 database unit tests
│   └── test_config.py   # 15 config unit tests
├── pyproject.toml       # Package metadata — `pip install .` → `tuido` CLI
├── tuido.bat            # Windows launcher
└── tuido.sh             # macOS / Linux launcher
```

---

## License

MIT © [Keerthi Pradyun](https://github.com/kpradyun)

*University of Hyderabad · Integrated M.Tech CSE · Expected June 2028*
