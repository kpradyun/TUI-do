# TUI-do Setup Guide

## Step 1 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2 — Create a Notion Integration

1. Go to **[notion.so/my-integrations](https://www.notion.so/my-integrations)**
2. Click **"New integration"**
3. Give it a name (e.g. `TUI-do`) and pick your workspace
4. Click **"Save"**
5. Copy the **"Internal Integration Secret"** — it starts with `ntn_...`

> ⚠️ Keep this token private. It gives read/write access to any database you connect it to.

---

## Step 3 — Connect the Integration to Your Database

This step is **required** — without it, the API will return a 404 even with a valid token.

1. Open your Kanban database in Notion
2. Click the **`···`** menu (top-right of the page)
3. Go to **Connections**
4. Search for and select your integration (`TUI-do`)
5. Click **Confirm**

---

## Step 4 — Get Your Database URL

1. Open your Kanban database in Notion (make sure you're viewing the **database**, not just a page inside it)
2. Copy the URL from your browser. It will look like:
   ```
   https://www.notion.so/319bd993cae180f2bcccded225180ac1?v=319bd993cae1801aac0d000cdd5dd920
   ```
   You can paste this URL as-is — TUI-do extracts the ID automatically.

---

## Step 5 — Configure Your Database Schema

TUI-do reads these specific Notion properties. Make sure your database has them:

| Property Name | Type | Notes |
| :--- | :--- | :--- |
| `Name` | Title | The task title (required) |
| `Status` | Status | Must have: `Not started`, `In progress`, `Done` |
| `Tags` | Multi-select | Optional, used for fuzzy filtering |
| `Description` | Text | Optional, renders as the task body |
| `Due Date` | Date | Flexible names: `Due`, `Deadline`, `Date` |
| `Priority` | Select | Flexible names: `Level`, `Urgency` |
| `Assign` | Person | Flexible names: `Assignee`, `Assigned to`, `Owner` |

> ℹ️ **Smart Mapping**: TUI-do automatically scans your database for these types. Even if your property is named "Responsible Person", as long as its type is **Person**, TUI-do will find it!

---

## Step 6 — Run the App

```bash
python main.py
```

On first run, TUI-do shows the **Configuration screen**. Enter:

- **Notion Integration Secret** → your `ntn_...` token from Step 2
- **Notion Database URL** → the URL from Step 4

Click **Authenticate Workspace**. The board loads and syncs immediately.

---

## Changing Your Configuration Later

If you need to update your token or switch to a different database, open the command palette from within the app and type:

```
:config
```

This reopens the setup screen. Save the new credentials and the board reloads automatically.

---

## Quick Reference

| Key / Command | Action |
| :--- | :--- |
| `n` | New task |
| `Enter` | Edit focused task (View Sub-tasks & Comments) |
| `[` / `]` | Move task left / right |
| `u` | Undo last move |
| `x` | Archive task (with confirm) |
| `r` | Refresh / sync now |
| `/` | Fuzzy Search (`/due:today`, `/assignee:name`, `/priority:high`) |
| `:new <title> [#tag]` | Create task from command line |
| `:switch <url_or_id>` | Seamlessly switch and cache a completely different Kanban board |
| `:export <file.md>` | Dump the entire remote board locally to Markdown |
| `:config` | Change token or database |
| `:help` | Show all commands |
| `:q` | Quit |

## Managing Multiple Boards

TUI-do is designed for multi-project workflows. You can seamlessly switch between different Notion databases:

1.  **Add a new board**: Type `:switch <Notion_URL>` in the command palette.
2.  **View all boards**: Type `:boards` to see your saved projects and their unique aliases.
3.  **Quick Toggle**: Type `:switch <alias>` (e.g., `:switch default`) to swap instantly.

Each board has its own isolated offline cache, so tasks from Project A will never clutter Project B.

## Troubleshooting

-   **404 Not Found**: Ensure you have **connected** the integration to the database (Step 3). This is the #1 cause of errors.
-   **Wrong Database ID**: Make sure you are copying the URL of the **Database** itself, not an individual page inside it.
-   **Missing Assignees**: Press **`r`** to force a full refresh. Ensure your Notion properties are of the correct **Type** (e.g. "Person" for assignees).
-   **No search results**: Search is case-insensitive. Try searching by prefix (e.g., `due:today`).

---

