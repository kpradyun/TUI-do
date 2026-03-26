# TUI-do: The Developer's Terminal Kanban
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**TUI-do** is a high-performance, keyboard-driven Kanban board for Notion, built specifically for developers who live in the terminal. It bridges the gap between your project management and your source code. It is currently being developed as an Integrated M.Tech CSE project at the University of Hyderabad.

## Features

* **Offline-First Architecture**: Powered by a local SQLite cache. View and edit your board instantly, even without an internet connection.
* **Vim-Style Navigation**: Navigate your board with `h`, `j`, `k`, `l` or arrow keys. Keep your hands on the home row.
* **Vim-Style Command Palette**: Use `:` to trigger powerful commands like `:new`, `:refresh`, `:export`, and `:switch`.
* **Smart Multi-criteria Filtering**: Press `/` to instantly filter tasks by title, `#tags`, `due:today`, `assignee:name`, or `priority:high`. Combine them like `due:today bug`!
* **Kanban Metadata**: Full read/write support for Due Dates, Priorities, Assignees, Comments, and Checklists.
* **60s Auto-Sync Heartbeat**: The app heartbeats every minute in the background, keeping your local board live without manual refreshes.
* **Optimistic UI Sync**: Changes are reflected in the UI instantly and synced to Notion in the background using a multi-threaded sync engine.
* **Multi-Board Management**: Seamlessly swap between different Notion databases and projects with full offline isolation.
* **Real-time Network Awareness**: Automatically detects internet status and triggers synchronization when reconnection is established.


## Architecture

TUI-do is designed with a decoupled, enterprise-grade architecture to ensure long-term maintainability:

* **`ui/`**: A modular Textual-based interface layer.
* **`db.py`**: A local SQLite persistence layer that handles offline queuing and caching.
* **`api.py`**: A dedicated Notion API worker that manages background synchronization.
* **`config.py`**: Global configuration management for user credentials.

## Installation

For a full step-by-step setup guide (creating the Notion integration, connecting it to your database, schema requirements), see **[SETUP.md](SETUP.md)**.

**Quick start:**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kpradyun/TUI-do.git
   cd TUI-do
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```
   On first run, TUI-do will walk you through connecting your Notion workspace.

## Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `n` | Create a new task with full details |
| `Enter` | View Sub-tasks, Comments, and Edit Task |
| `[` / `]` | Move task between columns |
| `u` | Undo last move |
| `x` | Archive/Delete task (confirm dialog) |
| `r` | Refresh / Full Sync (Cloud ⇄ Local) |
| `/` | Search/Filter tasks (use Space for multiple terms) |
| `?` | Open Help Modal |
| `colon` | Open Command Palette |
| `d` | Toggle Dark/Light Mode |
| `q` | Quit |

## Command Palette

| Command | Action |
| :--- | :--- |
| `:new <title> [#tag]` | Create a task from the command line |
| `:refresh` / `:r` | Sync with Notion immediately |
| `:export <file.md>` | Export current board to a Markdown checklist |
| `:switch <url_or_alias>` | Switch to a different board (caching it locally) |
| `:boards` | List all saved boards and their aliases |
| `:config` | Change your Notion token or database URL |
| `:rm` / `:del` | Archive the focused task |
| `:help` | Show the help modal |
| `:q` / `:quit` | Quit the app |

## 🔍 Advanced Search Syntax

TUI-do's search engine supports complex, multi-fragment queries. Use prefixes to target specific properties:

- `due:today` or `due:overdue`
- `assignee:pradyun`
- `priority:high`
- `#tagname` (or just `tagname`)

**Example**: Type `/due:today feature` to find all feature requests due today across all columns.

## Contributing

This project is being developed by A. Srinidh and K. Pradyun for FOSS Hack. Issues, and feature requests are welcome!

*Developing at the University of Hyderabad, Integrated M.Tech CSE, Expected Graduation: June 2028.*
