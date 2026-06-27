"""Samantha's Book Library — Tkinter GUI entry point.

Layout (top to bottom inside the VictorianFrame):
  1. Header (title + decorative subtitle)
  2. Summary row — unique titles and total copies
  3. Treeview listing the library with separate Signed, Special Edition,
     and Type columns so each edition flag is immediately visible.
  4. Add/remove form — title (autocomplete), SKU, quantity, author,
     signed & special-edition checkboxes.

Themes
------
  View > Theme > Victorian  — warm parchment / mahogany / gold
  View > Theme > Forest     — body-rot horror (near-black violet,
                               bruise-purple, sickly moss, bone text)

The active theme is persisted via database.get_pref / set_pref and
restored on next launch.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from book_store import add_book, load_books, remove_book, total_count, unique_titles
from autocomplete import AutocompleteEntry
from database import PREF_KEY_THEME, get_pref, set_pref
from fonts import DISPLAY_FAMILY, BODY_FAMILY
from theme import ThemeManager, build_themes

APP_TITLE = "Samantha's Book Library"

# Glyphs used in the edition columns
GLYPH_SIGNED  = "✦ Yes"
GLYPH_SPECIAL = "❖ Yes"
GLYPH_NONE    = "—"

TYPE_SIGNED_SPECIAL = "Signed Special Edition"
TYPE_SIGNED         = "Signed"
TYPE_SPECIAL        = "Special Edition"
TYPE_REGULAR        = "Regular"

VICTORIAN_THEME, FOREST_THEME = build_themes(DISPLAY_FAMILY, BODY_FAMILY)
_THEMES = {t.name: t for t in (VICTORIAN_THEME, FOREST_THEME)}


class VictorianFrame(tk.Frame):
    """Double-bordered panel whose border + interior colours are theme-aware."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, padx=2, pady=2, **kwargs)
        self.inner = tk.Frame(self, padx=14, pady=14)
        self.inner.pack(fill=tk.BOTH, expand=True)

    def set_theme(self, border_color: str, surface_color: str) -> None:
        """Recolor border and inner surface to match the active theme."""
        self.configure(bg=border_color)
        self.inner.configure(bg=surface_color)


class BookInventoryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x740")
        self.root.minsize(880, 580)

        # Active theme — restored from prefs, defaulting to Victorian
        saved = get_pref(PREF_KEY_THEME, VICTORIAN_THEME.name)
        self.theme = _THEMES.get(saved, VICTORIAN_THEME)

        # Tk variables backing the edition checkboxes
        self.signed_var  = tk.BooleanVar(value=False)
        self.special_var = tk.BooleanVar(value=False)

        self._build_ui()

        # Apply theme after widgets exist
        ThemeManager(self).apply(self.theme)

        self._build_menu()
        self.refresh_list()

    # ── Styles ───────────────────────────────────────────────────────────────

    def _configure_styles(self) -> None:
        """Rebuild all ttk styles and Treeview tags for the current theme."""
        c = self.theme.colors
        f = self.theme.fonts
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "App.Treeview",
            background=c.surface,
            foreground=c.text,
            fieldbackground=c.surface,
            bordercolor=c.border,
            lightcolor=c.border,
            darkcolor=c.accent,
            rowheight=30,
            font=f.body_f(),
        )
        style.configure(
            "App.Treeview.Heading",
            background=c.accent,
            foreground=c.text_on_accent,
            relief="flat",
            font=f.heading(),
        )
        style.map(
            "App.Treeview",
            background=[("selected", c.tag_selected_bg)],
            foreground=[("selected", c.tag_selected_fg)],
        )
        style.configure(
            "App.TEntry",
            fieldbackground=c.entry_bg,
            foreground=c.text,
            insertcolor=c.text,
            bordercolor=c.border,
            lightcolor=c.border,
            padding=6,
        )
        style.configure(
            f"{self.theme.name}.TCheckbutton",
            background=c.surface,
            foreground=c.text,
            font=f.body_f(),
            focuscolor=c.border_hi,
        )
        style.map(
            f"{self.theme.name}.TCheckbutton",
            background=[("active", c.surface)],
            indicatorcolor=[("selected", c.accent), ("!selected", c.entry_bg)],
        )

        # Treeview row tags
        self.tree.tag_configure("signed_special",
            background=c.tag_signed_special_bg, foreground=c.tag_signed_special_fg,
            font=f.badge())
        self.tree.tag_configure("signed_only",
            background=c.tag_signed_bg, foreground=c.tag_signed_fg,
            font=f.badge())
        self.tree.tag_configure("special_only",
            background=c.tag_special_bg, foreground=c.tag_special_fg,
            font=f.badge())
        self.tree.tag_configure("regular",
            background=c.tag_regular_bg, foreground=c.tag_regular_fg)

        # Restyle Treeview widget itself
        self.tree.configure(style="App.Treeview")

        # Restyle all Entry widgets
        for entry in (self.sku_entry, self.quantity_entry, self.author_entry):
            entry.configure(style="App.TEntry")
        self.title_entry.configure(style="App.TEntry")

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        """Add a View > Theme menu to the root window."""
        menubar = tk.Menu(self.root)
        view_menu = tk.Menu(menubar, tearoff=False)
        self._theme_var = tk.StringVar(value=self.theme.name)

        for name in _THEMES:
            view_menu.add_radiobutton(
                label=name,
                variable=self._theme_var,
                value=name,
                command=lambda n=name: self._set_theme(n),
            )

        menubar.add_cascade(label="View", menu=view_menu)
        self.root.configure(menu=menubar)

    def _set_theme(self, name: str) -> None:
        """Switch to theme *name*, persist the choice, and redraw."""
        self.theme = _THEMES[name]
        ThemeManager(self).apply(self.theme)
        set_pref(PREF_KEY_THEME, name)
        self.refresh_list()

    # ── UI build ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct all widgets. Colors are set by ThemeManager.apply() after."""
        self.outer = tk.Frame(self.root, padx=20, pady=20)
        self.outer.pack(fill=tk.BOTH, expand=True)

        self.shell = VictorianFrame(self.outer)
        self.shell.pack(fill=tk.BOTH, expand=True)
        main = self.shell.inner
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        # ── Header ───────────────────────────────────────────────────────────
        self.header_frame = tk.Frame(main)
        self.header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 6))

        self.title_label = tk.Label(self.header_frame, text=APP_TITLE)
        self.title_label.pack()

        self.subtitle_label = tk.Label(
            self.header_frame, text="❦   I HOPE YOU LIKE THIS <3   ❦"
        )
        self.subtitle_label.pack(pady=(4, 0))

        self.divider = tk.Frame(main, height=2)
        self.divider.grid(row=1, column=0, sticky=tk.EW, pady=(10, 12))

        # ── Summary row ──────────────────────────────────────────────────────
        self.summary_row = tk.Frame(main)
        self.summary_row.grid(row=2, column=0, sticky=tk.EW, pady=(0, 10))

        self.summary_header = tk.Label(self.summary_row, text="Collection at a glance")
        self.summary_header.pack(side=tk.LEFT)

        self.summary_label = tk.Label(self.summary_row, text="")
        self.summary_label.pack(side=tk.RIGHT)

        # ── Treeview ─────────────────────────────────────────────────────────
        self.list_panel_shell = VictorianFrame(main)
        self.list_panel_shell.grid(row=3, column=0, sticky=tk.NSEW, pady=(0, 12))

        columns = ("title", "author", "quantity", "signed", "special_edition", "type")
        self.tree = ttk.Treeview(
            self.list_panel_shell.inner,
            columns=columns,
            show="headings",
            height=8,
            style="App.Treeview",
        )
        self.tree.heading("title",           text="Volume Title")
        self.tree.heading("author",          text="Author")
        self.tree.heading("quantity",        text="Copies")
        self.tree.heading("signed",          text="Signed")
        self.tree.heading("special_edition", text="Special Ed.")
        self.tree.heading("type",            text="Type")

        self.tree.column("title",           width=260, anchor=tk.W)
        self.tree.column("author",          width=200, anchor=tk.W)
        self.tree.column("quantity",        width=60,  anchor=tk.CENTER)
        self.tree.column("signed",          width=80,  anchor=tk.CENTER)
        self.tree.column("special_edition", width=90,  anchor=tk.CENTER)
        self.tree.column("type",            width=180, anchor=tk.W)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # ── Form ─────────────────────────────────────────────────────────────
        self.form_outer = tk.Frame(main)
        self.form_outer.grid(row=4, column=0, sticky=tk.EW)

        self.form_heading = tk.Label(self.form_outer, text="Register a Volume")
        self.form_heading.pack(anchor=tk.W, pady=(0, 8))

        self.form_panel_shell = VictorianFrame(self.form_outer)
        self.form_panel_shell.pack(fill=tk.X)
        form = self.form_panel_shell.inner

        lbl_title    = tk.Label(form, text="Title")
        lbl_author   = tk.Label(form, text="Author")
        lbl_sku      = tk.Label(form, text="SKU")
        lbl_quantity = tk.Label(form, text="Quantity")
        self.form_labels = [lbl_title, lbl_author, lbl_sku, lbl_quantity]

        lbl_title.grid(   row=0, column=0, sticky=tk.W, padx=(0, 10), pady=6)
        lbl_author.grid(  row=1, column=0, sticky=tk.W, padx=(0, 10), pady=6)
        lbl_sku.grid(     row=2, column=0, sticky=tk.W, padx=(0, 10), pady=6)
        lbl_quantity.grid(row=2, column=2, sticky=tk.W, padx=(20, 10), pady=6)

        self.title_entry = AutocompleteEntry(
            form, width=42, style="App.TEntry",
            on_select=self._on_title_suggestion,
        )
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=6)

        self.author_entry = ttk.Entry(form, width=30, style="App.TEntry")
        self.author_entry.grid(row=1, column=1, sticky=tk.W, pady=6)

        self.sku_entry = ttk.Entry(form, width=20, style="App.TEntry")
        self.sku_entry.grid(row=2, column=1, sticky=tk.W, pady=6)

        self.quantity_entry = ttk.Entry(form, width=10, style="App.TEntry")
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(row=2, column=3, sticky=tk.W, pady=6)

        self.signed_check = ttk.Checkbutton(
            form, text="Signed by the author",
            variable=self.signed_var, style="Victorian.TCheckbutton",
        )
        self.signed_check.grid(row=3, column=0, columnspan=2, sticky=tk.W,
                               padx=(0, 20), pady=(4, 8))

        self.special_check = ttk.Checkbutton(
            form, text="Special edition",
            variable=self.special_var, style="Victorian.TCheckbutton",
        )
        self.special_check.grid(row=3, column=2, columnspan=2, sticky=tk.W, pady=(4, 8))

        self.button_row = tk.Frame(form)
        self.button_row.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=(10, 0))

        btn_add    = self._make_button(self.button_row, "Add to Library",  self.on_add)
        btn_remove = self._make_button(self.button_row, "Remove Selected", self.on_remove)
        btn_add.pack(side=tk.LEFT, padx=(0, 10))
        btn_remove.pack(side=tk.LEFT)
        self.action_buttons = [btn_add, btn_remove]

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self.title_entry.bind("<Return>",    self._on_title_return)
        self.author_entry.bind("<Return>",   lambda _e: self.on_add())
        self.sku_entry.bind("<Return>",      lambda _e: self.on_add())
        self.quantity_entry.bind("<Return>", lambda _e: self.on_add())

        self.footer_label = tk.Label(main, text="— EST 1997 —")
        self.footer_label.grid(row=5, column=0, pady=(14, 0))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _on_title_suggestion(self, suggestion: dict) -> None:
        """Auto-fill SKU and Author when an autocomplete suggestion is selected."""
        sku = suggestion.get("sku", "")
        if sku:
            self.sku_entry.delete(0, tk.END)
            self.sku_entry.insert(0, sku)
        author = suggestion.get("author", "")
        if author and not self.author_entry.get().strip():
            self.author_entry.delete(0, tk.END)
            self.author_entry.insert(0, author)

    def _make_button(self, master: tk.Misc, text: str, command) -> tk.Button:
        """Create a styled action button (colors applied by ThemeManager)."""
        return tk.Button(
            master, text=text, command=command,
            relief=tk.RAISED, bd=2,
            highlightthickness=1,
            padx=12, pady=4, cursor="hand2",
        )

    @staticmethod
    def _row_meta(signed: bool, special: bool) -> tuple[str, str, str, str]:
        """Return (tag, signed_text, special_text, type_label) for a book row."""
        if signed and special:
            return "signed_special", GLYPH_SIGNED, GLYPH_SPECIAL, TYPE_SIGNED_SPECIAL
        if signed:
            return "signed_only",    GLYPH_SIGNED, GLYPH_NONE,    TYPE_SIGNED
        if special:
            return "special_only",   GLYPH_NONE,   GLYPH_SPECIAL, TYPE_SPECIAL
        return     "regular",        GLYPH_NONE,   GLYPH_NONE,    TYPE_REGULAR

    def refresh_list(self) -> None:
        """Reload books from the database and repopulate the Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        books = load_books()
        for book in books:
            tag, signed_text, special_text, type_label = self._row_meta(
                book["signed"], book["special_edition"]
            )
            self.tree.insert(
                "", tk.END, iid=str(book["id"]),
                values=(
                    book["title"],
                    book.get("author", ""),
                    book["quantity"],
                    signed_text,
                    special_text,
                    type_label,
                ),
                tags=(tag,),
            )

        n_titles = unique_titles(books)
        copies   = total_count(books)
        self.summary_label.config(
            text=(
                f"{n_titles} title{'s' if n_titles != 1 else ''}"
                f"  ·  {copies} total cop{'ies' if copies != 1 else 'y'}"
            )
        )

    def _parse_quantity(self) -> int:
        """Parse the quantity field; default 1 if empty. Raises ValueError if invalid."""
        text = self.quantity_entry.get().strip()
        if not text:
            return 1
        if not text.isdigit() or int(text) < 1:
            raise ValueError(
                f'"{text}" is not a valid quantity. '
                "Please enter a whole number greater than zero."
            )
        return int(text)

    def _on_title_return(self, _event: tk.Event) -> str:
        self.on_add()
        return "break"

    def on_add(self) -> None:
        """Read the form fields and add a book to the inventory."""
        title  = self.title_entry.get_title()
        sku    = self.sku_entry.get().strip() or self.title_entry.get_sku() or None
        author = self.author_entry.get().strip() or None
        try:
            quantity = self._parse_quantity()
            add_book(
                title, quantity,
                sku=sku,
                signed=self.signed_var.get(),
                special_edition=self.special_var.get(),
                author=author,
            )
        except ValueError as error:
            messagebox.showerror("Invalid Entry", str(error))
            return

        self.title_entry.clear()
        self.sku_entry.delete(0, tk.END)
        self.author_entry.delete(0, tk.END)
        self.quantity_entry.delete(0, tk.END)
        self.quantity_entry.insert(0, "1")
        self.signed_var.set(False)
        self.special_var.set(False)
        self.refresh_list()

    def on_remove(self) -> None:
        """Remove one copy of the selected book from the inventory."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Pray select a volume from the catalogue.")
            return

        item_id    = selected[0]
        values     = self.tree.item(item_id, "values")
        title      = values[0]
        quantity   = values[2]
        type_label = values[5]

        qty = int(quantity)
        copy_word = "copy" if qty == 1 else "copies"
        prompt = (
            f'Remove 1 of {qty} {copy_word} of "{title}" ({type_label}) from the library?'
        )
        if not messagebox.askyesno("Remove Volume", prompt):
            return

        try:
            remove_book(int(item_id))
        except ValueError as error:
            messagebox.showerror("Could Not Remove", str(error))
            return

        self.refresh_list()


def main() -> None:
    root = tk.Tk()
    BookInventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()