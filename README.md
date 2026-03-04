# TUI-do: The Developer's Terminal Kanban

**TUI-do** is a high-performance, keyboard-driven Kanban board for Notion, built specifically for developers who live in the terminal. It bridges the gap between your project management and your source code. It is currently being developed as an Integrated M.Tech CSE project at the University of Hyderabad.

## Features

* **Offline-First Architecture**: Powered by a local SQLite cache. View and edit your board instantly, even without an internet connection.
* **Vim-Style Navigation**: Navigate your board with `h`, `j`, `k`, `l` or arrow keys. Keep your hands on the home row.
* **Vim-Style Command Palette**: Use `:` to trigger powerful commands like `:new`, `:refresh`, and `:q`.
* **Smart Filtering**: Press `/` to instantly filter tasks by title or `#tags`.
* **Optimistic UI Sync**: Changes are reflected in the UI instantly and synced to Notion in the background using a multi-threaded sync engine.
* **Real-time Network Awareness**: Automatically detects internet status and triggers synchronization when reconnection is established.
* **Automatic Configuration**: No need to mess with `.env` files. TUI-do handles your credentials securely through a native setup screen.

## Architecture

TUI-do is designed with a decoupled, enterprise-grade architecture to ensure long-term maintainability:

* **`ui/`**: A modular Textual-based interface layer.
* **`db.py`**: A local SQLite persistence layer that handles offline queuing and caching.
* **`api.py`**: A dedicated Notion API worker that manages background synchronization.
* **`config.py`**: Global configuration management for user credentials.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/tui-do.git
   cd tui-do
   ```

2. **Install dependencies:**
   ```bash
   pip install textual notion-client
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

## Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `n` | Create a new task with full details |
| `Enter` | View and edit task description |
| `[` / `]` | Move task between columns |
| `x` | Archive/Delete task |
| `/` | Search/Filter tasks |
| `:` | Open Command Palette |
| `d` | Toggle Dark/Light Mode |
| `q` | Quit |

## Roadmap

- [ ] **Git Context Awareness**: Automatically highlight tasks based on your current local git branch.
- [ ] **Assignee Avatars**: Display task owners directly on the cards.
- [ ] **Pomodoro Time Tracking**: Integrated time tracking for active tasks.
- [ ] **Local SQLite Caching**: Full offline-to-online conflict resolution.

## Contributing

This project is being developed by A. Srinidh and K. Pradyun for FOSS Hack. Issues, and feature requests are welcome!

*Developing at the University of Hyderabad, Expected Graduation: June 2028.*
