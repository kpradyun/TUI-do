# TUI-do: The Developer's Terminal Kanban

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-8A2BE2)](https://textual.textualize.io/)

**TUI-do** is a high-performance, keyboard-driven Kanban board for Notion, built specifically for developers who live in the terminal. It bridges the gap between your project management and your source code.

> Developed as an Integrated M.Tech CSE project at the University of Hyderabad for FOSS Hack.

---

## What This Project Demonstrates

- Offline-first architecture with SQLite + optimistic UI sync
- Real-time Notion API integration with background sync threading
- Terminal UI built on [Textual](https://textual.textualize.io/) with Vim-style navigation
- Secure credential storage (OS config dir, `0o600` permissions)
- Multi-board management with local caching and reconnect logic
- Advanced multi-criteria filter parsing (`due:today #tag priority:high`)

---

## Features

- **Offline-First** — SQLite local cache; view and edit without internet
- **Vim-Style Navigation** — `h`, `j`, `k`, `l` or arrow keys
- **Command Palette** — `:` to trigger commands like `:new`, `:refresh`, `:export`
- **Smart Filtering** — `/` to filter by title, `#tags`, `due:today`, `assignee:name`, `priority:high`
- **60s Auto-Sync** — Background heartbeat keeps local board live
- **Optimistic UI** — Changes appear instantly, sync happens in the background
- **Multi-Board** — Seamlessly switch between Notion databases
- **Network Awareness** — Auto-reconnects and syncs when internet is restored

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Textual TUI (ui/)                  │
│   Kanban Board · Command Palette · Filter Engine    │
└──────────────────────┬──────────────────────────────┘
                       │ read/write
┌──────────────────────▼──────────────────────────────┐
│              SQLite Local Cache (db.py)             │
│   tasks · offline_queue · boards · sync_log         │
└──────────────────────┬──────────────────────────────┘
                       │ background thread (60s)
┌──────────────────────▼──────────────────────────────┐
│           Notion API Worker (api.py)                │
│   create · update · move · archive · sync           │
└─────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Python 3.10 or higher
- A **Notion account** (free tier works)
- A Notion Integration token and a database shared with it (see [SETUP.md](SETUP.md))

---

## Installation

```bash
git clone https://github.com/kpradyun/TUI-do.git
cd TUI-do

python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

---

## First Run

```bash
python main.py
```

On first run, TUI-do walks you through connecting your Notion workspace:
1. Enter your Notion Integration token (starts with `secret_` or `ntn_`)
2. Enter your Notion database URL
3. The app syncs and opens your board

Credentials are stored securely in `~/.config/tuido/config.json` (permissions: `0o600`). They are **never** written to the project directory.

For detailed Notion setup instructions (creating the integration, sharing the database, required schema), see **[SETUP.md](SETUP.md)**.

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `h` / `j` / `k` / `l` or arrows | Navigate board |
| `n` | Create new task |
| `Enter` | View/edit task details |
| `[` / `]` | Move task between columns |
| `u` | Undo last move |
| `x` | Archive/delete task |
| `r` | Refresh / full sync |
| `/` | Search and filter |
| `?` | Help modal |
| `:` | Command palette |
| `d` | Toggle dark/light mode |
| `q` | Quit |

---

## Command Palette

| Command | Action |
|---|---|
| `:new <title> [#tag]` | Create task from command line |
| `:refresh` / `:r` | Sync with Notion now |
| `:export <file.md>` | Export board to Markdown |
| `:switch <url_or_alias>` | Switch to a different board |
| `:boards` | List all saved boards |
| `:config` | Update token or database URL |
| `:rm` / `:del` | Archive focused task |
| `:help` | Show help |
| `:q` / `:quit` | Quit |

---

## Filter Syntax

Press `/` and type any combination:

| Syntax | Description |
|---|---|
| `bug` | Filter by title text |
| `#tagname` | Filter by tag |
| `due:today` | Tasks due today |
| `due:overdue` | Overdue tasks |
| `priority:high` | Filter by priority |
| `assignee:name` | Filter by assignee |

Combine freely: `due:today #feature priority:high`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Invalid token" on first run | Ensure token starts with `secret_` or `ntn_` |
| Board shows empty | Check the database is shared with your integration in Notion |
| Tasks not syncing | Check internet; run `:refresh` manually |
| Schema error | See [SETUP.md](SETUP.md) for required Notion database properties |
| Config reset needed | Delete `~/.config/tuido/config.json` and re-run |

---

## Contributing

Issues and pull requests are welcome! This project is by A. Srinidh and K. Pradyun.

*University of Hyderabad · Integrated M.Tech CSE · Expected June 2028*

---

## License

MIT © [kpradyun](https://github.com/kpradyun)
