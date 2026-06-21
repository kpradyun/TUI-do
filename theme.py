"""
Theme support — load color overrides from ~/.config/tuido/theme.json.

Sample theme.json:
{
  "accent":  "#f0c040",
  "success": "#00cc66",
  "error":   "#ff4444",
  "warning": "#ff8800",
  "primary": "#7b8cde"
}

Keys map directly to Textual CSS design-token variables.
Run  :theme-reset  inside the app to regenerate a default file.
"""
from __future__ import annotations

import json
from pathlib import Path

_THEME_PATH = Path.home() / ".config" / "tuido" / "theme.json"

_DEFAULTS: dict[str, str] = {
    "accent":  "#f0c040",
    "success": "#00cc66",
    "error":   "#ff4444",
    "warning": "#ff8800",
    "primary": "#7b8cde",
}


def load() -> dict[str, str]:
    """Return theme overrides, or {} if no theme file exists."""
    if not _THEME_PATH.exists():
        return {}
    try:
        with open(_THEME_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: str(v) for k, v in data.items() if isinstance(k, str)}
    except Exception:
        return {}


def write_defaults() -> None:
    """Write a sample theme.json so the user has something to edit."""
    _THEME_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _THEME_PATH.exists():
        with open(_THEME_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFAULTS, f, indent=2)


def build_css(overrides: dict[str, str]) -> str:
    """
    Convert theme.json color overrides into concrete Textual CSS rules.

    Textual resolves $variables at parse time, so we can't set them
    dynamically. Instead we target specific widgets directly.
    """
    if not overrides:
        return ""

    lines = ["/* TUI-do custom theme */"]

    accent = overrides.get("accent", "")
    success = overrides.get("success", "")
    error = overrides.get("error", "")
    warning = overrides.get("warning", "")
    primary = overrides.get("primary", "")

    if accent:
        lines.append(f"KanbanColumn:focus-within {{ border: thick {accent}; }}")
        lines.append(f"TaskCard:focus {{ border-left: thick {accent}; }}")
        lines.append(f".dialog-title {{ color: {accent}; }}")

    if success:
        lines.append(f"TaskCard:hover {{ border-left: thick {success}; }}")

    if error:
        lines.append(f"TaskCard.overdue-card {{ border-left: thick {error}; }}")
        lines.append(f"KanbanColumn.wip-exceeded {{ border: thick {error}; }}")

    if warning:
        lines.append(f"TaskCard.pending {{ border-left: thick {warning}; }}")

    if primary:
        lines.append(f".tag {{ background: {primary}; }}")

    result = "\n".join(lines) + "\n"
    # Return empty string if we only produced the comment (no real overrides matched)
    return result if len(lines) > 1 else ""
