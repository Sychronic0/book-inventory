"""AutocompleteEntry — a ttk.Entry that suggests books as you type.

Built on a popup Listbox positioned beneath the entry. Behavior:
  - Debounces keystrokes by 300ms before calling search_books.
  - Up/Down arrows move the highlighted suggestion; Enter accepts it.
  - Selecting a suggestion calls back to the host with the full dict
    (title, author, sku, source_id) and stashes sku/title for retrieval
    via get_sku() / get_title().
  - Escape or FocusOut (after a short grace period) hides the popup.

Color palette is shared with main.py for visual consistency.
"""

import tkinter as tk
from tkinter import ttk

from book_search import search_books

# Neutral fallback colours used when no theme provider is set.
_DEFAULT_COLORS = {
    "bg": "#faf0dc",
    "fg": "#2a1a12",
    "select_bg": "#8b6914",
    "select_fg": "#f5e6c8",
    "border": "#c9a227",
    "border_hi": "#e8c547",
    "scrollbar_bg": "#f5e6c8",
    "scrollbar_active": "#8b6914",
}

VISIBLE_SUGGESTIONS = 8


class AutocompleteEntry(ttk.Entry):
    """Entry field that suggests book titles from the catalog as you type."""

    def __init__(self, master: tk.Misc, on_select=None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._after_id: str | None = None
        self._hide_after_id: str | None = None
        self._suggestions: list[dict] = []
        self._popup_frame: tk.Frame | None = None
        self._popup: tk.Listbox | None = None
        self._scrollbar: tk.Scrollbar | None = None
        self._selected_title = ""
        self._selected_sku = ""
        self._active_index = -1

        self._theme_provider = None  # callable returning color dict
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<FocusOut>", self._schedule_hide_popup)
        self.bind("<Escape>", lambda _event: self._hide_popup())
        self.bind("<Return>", self._accept_typed_or_selected)

    def get_title(self) -> str:
        return self._selected_title or self.get().strip()

    def get_sku(self) -> str:
        return self._selected_sku

    def set_theme_provider(self, provider) -> None:
        """Set a callable that returns the current theme colour dict.

        The dict should have keys: bg, fg, select_bg, select_fg,
        border, border_hi, scrollbar_bg, scrollbar_active.
        """
        self._theme_provider = provider

    def _theme_colors(self) -> dict:
        """Return current theme colours, falling back to neutral defaults."""
        if self._theme_provider is not None:
            try:
                return self._theme_provider()
            except Exception:
                pass
        return _DEFAULT_COLORS

    def clear(self) -> None:
        self.delete(0, tk.END)
        self._selected_title = ""
        self._selected_sku = ""
        self._active_index = -1
        self._hide_popup()

    def _on_key_press(self, event: tk.Event) -> str | None:
        if self._popup is None:
            if event.keysym == "Down":
                return self._focus_popup(event)
            return None

        if event.keysym == "Down":
            self._move_selection(1)
            return "break"
        if event.keysym == "Up":
            self._move_selection(-1)
            return "break"
        if event.keysym == "Return":
            return self._accept_typed_or_selected(event)
        if event.keysym == "Escape":
            self._hide_popup()
            return "break"
        return None

    def _on_key_release(self, event: tk.Event) -> None:
        if event.keysym in {"Up", "Down", "Return", "Escape", "Tab"}:
            return

        if self._after_id is not None:
            self.after_cancel(self._after_id)

        self._selected_title = ""
        self._selected_sku = ""
        query = self.get().strip()
        if len(query) < 2:
            self._hide_popup()
            return

        self._after_id = self.after(300, lambda: self._fetch_suggestions(query))

    def _fetch_suggestions(self, query: str) -> None:
        self._after_id = None
        if query != self.get().strip():
            return

        self._suggestions = search_books(query)
        if not self._suggestions:
            self._hide_popup()
            return

        self._show_popup([item["display"] for item in self._suggestions])

    def _show_popup(self, items: list[str]) -> None:
        self._hide_popup()
        self._active_index = 0

        _c = self._theme_colors()
        self._popup_frame = tk.Frame(
            self.master,
            bg=_c["border"],
            highlightthickness=1,
            highlightbackground=_c["border_hi"],
        )

        self._popup = tk.Listbox(
            self._popup_frame,
            height=VISIBLE_SUGGESTIONS,
            activestyle="none",
            bg=_c["bg"],
            fg=_c["fg"],
            selectbackground=_c["select_bg"],
            selectforeground=_c["select_fg"],
            highlightthickness=0,
            font=("Georgia", 10),
            exportselection=False,
        )
        self._scrollbar = tk.Scrollbar(
            self._popup_frame,
            orient=tk.VERTICAL,
            command=self._popup.yview,
            troughcolor=_c["scrollbar_bg"],
            activebackground=_c["scrollbar_active"],
            highlightthickness=0,
        )
        self._popup.configure(yscrollcommand=self._scrollbar.set)

        for item in items:
            self._popup.insert(tk.END, item)

        self._popup.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._popup.bind("<ButtonRelease-1>", self._select_from_popup)
        self._popup.bind("<Return>", self._select_from_popup)
        self._popup.bind("<MouseWheel>", self._on_mousewheel)
        self._popup.bind("<Button-4>", self._on_mousewheel_linux)
        self._popup.bind("<Button-5>", self._on_mousewheel_linux)
        self._popup_frame.bind("<MouseWheel>", self._on_mousewheel)
        self._popup_frame.bind("<Button-4>", self._on_mousewheel_linux)
        self._popup_frame.bind("<Button-5>", self._on_mousewheel_linux)

        entry_x = self.winfo_x()
        entry_y = self.winfo_y() + self.winfo_height()
        entry_width = self.winfo_width()

        self._popup_frame.place(x=entry_x, y=entry_y, width=entry_width + 18)
        self._popup_frame.lift()
        self._highlight_index(0)

    def _on_mousewheel(self, event: tk.Event) -> str:
        if self._popup is not None:
            self._popup.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_mousewheel_linux(self, event: tk.Event) -> str:
        if self._popup is not None:
            direction = -1 if event.num == 4 else 1
            self._popup.yview_scroll(direction, "units")
        return "break"

    def _schedule_hide_popup(self, _event: tk.Event | None = None) -> None:
        if self._hide_after_id is not None:
            self.after_cancel(self._hide_after_id)
        self._hide_after_id = self.after(150, self._maybe_hide_popup)

    def _maybe_hide_popup(self) -> None:
        self._hide_after_id = None
        focus = self.winfo_toplevel().focus_get()
        if focus is None:
            self._hide_popup()
            return

        widget = str(focus)
        popup_widgets = {str(self._popup_frame), str(self._popup), str(self._scrollbar)}
        if self._popup_frame is not None and widget in popup_widgets:
            return
        self._hide_popup()

    def _hide_popup(self, _event: tk.Event | None = None) -> None:
        if self._hide_after_id is not None:
            self.after_cancel(self._hide_after_id)
            self._hide_after_id = None
        if self._popup_frame is not None:
            self._popup_frame.destroy()
        self._popup_frame = None
        self._popup = None
        self._scrollbar = None
        self._active_index = -1

    def _focus_popup(self, _event: tk.Event) -> str:
        if self._popup is not None:
            self._highlight_index(max(self._active_index, 0))
            return "break"
        return ""

    def _move_selection(self, delta: int) -> None:
        if not self._suggestions:
            return
        next_index = self._active_index + delta
        next_index = max(0, min(len(self._suggestions) - 1, next_index))
        self._highlight_index(next_index)

    def _highlight_index(self, index: int) -> None:
        if self._popup is None or not self._suggestions:
            return

        self._active_index = index
        self._popup.selection_clear(0, tk.END)
        self._popup.selection_set(index)
        self._popup.activate(index)
        self._popup.see(index)

    def _apply_suggestion(self, index: int) -> None:
        suggestion = self._suggestions[index]
        self._selected_title = suggestion["title"]
        self._selected_sku = suggestion.get("sku", "")
        self.delete(0, tk.END)
        self.insert(0, suggestion["title"])
        if self._on_select is not None:
            self._on_select(suggestion)

    def _select_from_popup(self, _event: tk.Event | None = None) -> None:
        if self._popup is None:
            return

        selection = self._popup.curselection()
        index = selection[0] if selection else self._active_index
        if index < 0:
            return

        self._apply_suggestion(index)
        self._hide_popup()

    def _accept_typed_or_selected(self, _event: tk.Event) -> str:
        if self._popup is not None and self._suggestions:
            index = self._active_index if self._active_index >= 0 else 0
            self._apply_suggestion(index)
            self._hide_popup()
            return "break"
        return ""