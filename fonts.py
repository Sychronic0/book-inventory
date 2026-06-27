"""Font resolution for the Book Inventory UI.

Resolves display and body font families at import time by spinning up a
throwaway Tk root and checking which families are installed. This means
the rest of the codebase can reference font names without worrying about
availability on the current machine.

Display ladder (title / headings):
    Cinzel → Trajan Pro → Bookman Old Style → Bookman →
    Garamond → Constantia → Georgia

Body ladder (labels, entries, table cells):
    Georgia → Garamond → Constantia → Times New Roman → TkDefaultFont

Both ladders fall back gracefully; the final fallback is always available.
"""

import tkinter as tk
from tkinter import font as tkfont

_DISPLAY_LADDER = [
    "Cinzel",
    "Trajan Pro",
    "Bookman Old Style",
    "Bookman",
    "Garamond",
    "Constantia",
    "Georgia",
]

_BODY_LADDER = [
    "Georgia",
    "Garamond",
    "Constantia",
    "Times New Roman",
    "TkDefaultFont",
]


def _resolve(ladder: list[str]) -> str:
    """Return the first family in *ladder* that is installed, or the last entry."""
    try:
        _root = tk.Tk()
        _root.withdraw()
        installed = set(tkfont.families(_root))
        _root.destroy()
    except Exception:
        return ladder[-1]

    for family in ladder:
        if family in installed:
            return family
    return ladder[-1]


# Resolved at import time — safe to use as module-level constants.
DISPLAY_FAMILY: str = _resolve(_DISPLAY_LADDER)
BODY_FAMILY: str = _resolve(_BODY_LADDER)
