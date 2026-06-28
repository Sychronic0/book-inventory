"""Samantha's Book Library — Tkinter GUI entry point.

Tabs:
  - Library  — header, summary, book list, add/remove form
  - Search   — live search across title/author/SKU/type with type filter

Extra:
  - "Browse All" button opens a fullscreen modal of the full collection
  - View > Theme switches between Victorian and Forest palettes (persisted)
"""

import tkinter as tk
from tkinter import messagebox, ttk

from book_store import add_book, load_books, remove_book, total_count, unique_titles
from autocomplete import AutocompleteEntry
from database import PREF_KEY_THEME, get_pref, set_pref
from fonts import DISPLAY_FAMILY, BODY_FAMILY
from theme import ThemeManager, build_themes

APP_TITLE = "Samantha's Book Library"

GLYPH_SIGNED  = "✦ Yes"
GLYPH_SPECIAL = "❖ Yes"
GLYPH_NONE    = "—"

TYPE_SIGNED_SPECIAL = "Signed Special Edition"
TYPE_SIGNED         = "Signed"
TYPE_SPECIAL        = "Special Edition"
TYPE_REGULAR        = "Regular"

VICTORIAN_THEME, FOREST_THEME = build_themes(DISPLAY_FAMILY, BODY_FAMILY)
_THEMES = {t.name: t for t in (VICTORIAN_THEME, FOREST_THEME)}

TREE_COLUMNS = ("title", "author", "quantity", "signed", "special_edition", "type")


class VictorianFrame(tk.Frame):
    """Double-bordered panel whose border + interior colours are theme-aware."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, padx=2, pady=2, **kwargs)
        self.inner = tk.Frame(self, padx=14, pady=14)
        self.inner.pack(fill=tk.BOTH, expand=True)

    def set_theme(self, border_color: str, surface_color: str) -> None:
        self.configure(bg=border_color)
        self.inner.configure(bg=surface_color)


class BookInventoryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x780")
        self.root.minsize(880, 600)

        saved = get_pref(PREF_KEY_THEME, VICTORIAN_THEME.name)
        self.theme = _THEMES.get(saved, VICTORIAN_THEME)

        self.signed_var  = tk.BooleanVar(value=False)
        self.special_var = tk.BooleanVar(value=False)
        self._search_after_id = None
        self._search_view = "table"  # "table" or "grid"

        self._build_ui()
        self._build_menu()
        ThemeManager(self).apply(self.theme)
        self.refresh_list()

    # ── Styles ───────────────────────────────────────────────────────────────

    def _configure_styles(self) -> None:
        c = self.theme.colors
        f = self.theme.fonts
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.Treeview",
            background=c.surface, foreground=c.text,
            fieldbackground=c.surface, bordercolor=c.border,
            lightcolor=c.border, darkcolor=c.border,
            rowheight=30, font=f.body_f())
        style.configure("App.Treeview.Heading",
            background=c.accent, foreground=c.text_on_accent,
            relief="flat", font=f.heading())
        style.map("App.Treeview",
            background=[("selected", c.tag_selected_bg)],
            foreground=[("selected", c.tag_selected_fg)])

        style.configure("App.TEntry",
            fieldbackground=c.entry_bg, foreground=c.text,
            insertcolor=c.text, bordercolor=c.border,
            lightcolor=c.border, darkcolor=c.border,
            relief="flat", padding=6)

        style.configure(f"{self.theme.name}.TCheckbutton",
            background=c.surface, foreground=c.text,
            font=f.body_f(), focuscolor=c.border_hi)
        style.map(f"{self.theme.name}.TCheckbutton",
            background=[("active", c.surface)],
            indicatorcolor=[("selected", c.accent), ("!selected", c.entry_bg)])

        style.configure("App.TNotebook",
            background=c.window_bg, borderwidth=0, tabmargins=0)
        style.configure("App.TNotebook.Tab",
            background=c.accent, foreground=c.text_on_accent,
            font=f.label(), padding=(16, 6), borderwidth=0,
            lightcolor=c.accent, darkcolor=c.accent)
        style.map("App.TNotebook.Tab",
            background=[("selected", c.surface), ("active", c.accent_hi)],
            foreground=[("selected", c.text)],
            lightcolor=[("selected", c.border)],
            darkcolor=[("selected", c.border)])

        for tree in (self.tree, self.search_tree):
            tree.tag_configure("signed_special",
                background=c.tag_signed_special_bg,
                foreground=c.tag_signed_special_fg, font=f.badge())
            tree.tag_configure("signed_only",
                background=c.tag_signed_bg,
                foreground=c.tag_signed_fg, font=f.badge())
            tree.tag_configure("special_only",
                background=c.tag_special_bg,
                foreground=c.tag_special_fg, font=f.badge())
            tree.tag_configure("regular",
                background=c.tag_regular_bg, foreground=c.tag_regular_fg)
            tree.configure(style="App.Treeview")

        for entry in (self.sku_entry, self.quantity_entry, self.author_entry,
                      self.search_entry):
            entry.configure(style="App.TEntry")
        self.title_entry.configure(style="App.TEntry")
        self.notebook.configure(style="App.TNotebook")

        if hasattr(self.title_entry, "set_theme_provider"):
            self.title_entry.set_theme_provider(lambda: {
                "bg": c.popup_bg, "fg": c.text,
                "select_bg": c.popup_select_bg, "select_fg": c.popup_select_fg,
                "border": c.border, "border_hi": c.border_hi,
                "scrollbar_bg": c.surface_alt, "scrollbar_active": c.accent_hi,
            })

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        view_menu = tk.Menu(menubar, tearoff=False)
        self._theme_var = tk.StringVar(value=self.theme.name)
        for name in _THEMES:
            view_menu.add_radiobutton(
                label=name, variable=self._theme_var, value=name,
                command=lambda n=name: self._set_theme(n))
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.configure(menu=menubar)

    def _set_theme(self, name: str) -> None:
        self.theme = _THEMES[name]
        ThemeManager(self).apply(self.theme)
        set_pref(PREF_KEY_THEME, name)
        self.refresh_list()

    # ── UI build ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.outer = tk.Frame(self.root, padx=16, pady=16)
        self.outer.pack(fill=tk.BOTH, expand=True)

        self.shell = VictorianFrame(self.outer)
        self.shell.pack(fill=tk.BOTH, expand=True)
        main = self.shell.inner
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(main, style="App.TNotebook")
        self.notebook.grid(row=0, column=0, sticky=tk.NSEW)

        self._build_library_tab()
        self._build_search_tab()

    def _build_library_tab(self) -> None:
        tab = tk.Frame(self.notebook)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        self.notebook.add(tab, text="  Library  ")
        self._library_tab = tab

        # Header
        self.header_frame = tk.Frame(tab)
        self.header_frame.grid(row=0, column=0, sticky=tk.EW, padx=16, pady=(12, 4))

        self.title_label = tk.Label(self.header_frame, text=APP_TITLE)
        self.title_label.pack()
        self.subtitle_label = tk.Label(
            self.header_frame, text="❦   I HOPE YOU LIKE THIS <3   ❦")
        self.subtitle_label.pack(pady=(4, 0))

        self.divider = tk.Frame(tab, height=2)
        self.divider.grid(row=1, column=0, sticky=tk.EW, padx=16, pady=(6, 8))

        # Summary + Browse All
        self.summary_row = tk.Frame(tab)
        self.summary_row.grid(row=2, column=0, sticky=tk.EW, padx=16, pady=(0, 6))

        self.summary_header = tk.Label(self.summary_row, text="Collection at a glance")
        self.summary_header.pack(side=tk.LEFT)

        self.browse_btn = tk.Button(
            self.summary_row, text="Browse All ↗",
            command=self._open_browse_overlay,
            cursor="hand2", relief=tk.FLAT, bd=0,
            padx=8, pady=2, highlightthickness=0)
        self.browse_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.summary_label = tk.Label(self.summary_row, text="")
        self.summary_label.pack(side=tk.RIGHT)

        # Treeview
        list_frame = tk.Frame(tab)
        list_frame.grid(row=3, column=0, sticky=tk.NSEW, padx=16, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree = self._make_treeview(list_frame)
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.tree.configure(yscrollcommand=scroll.set)

        # Form
        self.form_outer = tk.Frame(tab)
        self.form_outer.grid(row=4, column=0, sticky=tk.EW, padx=16, pady=(0, 8))

        self.form_heading = tk.Label(self.form_outer, text="Register a Volume")
        self.form_heading.pack(anchor=tk.W, pady=(0, 6))

        self.form_panel_shell = VictorianFrame(self.form_outer)
        self.form_panel_shell.pack(fill=tk.X)
        form = self.form_panel_shell.inner

        lbl_title    = tk.Label(form, text="Title")
        lbl_author   = tk.Label(form, text="Author")
        lbl_sku      = tk.Label(form, text="SKU")
        lbl_quantity = tk.Label(form, text="Quantity")
        self.form_labels = [lbl_title, lbl_author, lbl_sku, lbl_quantity]

        lbl_title.grid(   row=0, column=0, sticky=tk.W, padx=(0, 10), pady=4)
        lbl_author.grid(  row=1, column=0, sticky=tk.W, padx=(0, 10), pady=4)
        lbl_sku.grid(     row=2, column=0, sticky=tk.W, padx=(0, 10), pady=4)
        lbl_quantity.grid(row=2, column=2, sticky=tk.W, padx=(20, 10), pady=4)

        self.title_entry = AutocompleteEntry(
            form, width=42, style="App.TEntry",
            on_select=self._on_title_suggestion)
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=4)

        self.author_entry = ttk.Entry(form, width=30, style="App.TEntry")
        self.author_entry.grid(row=1, column=1, sticky=tk.W, pady=4)

        self.sku_entry = ttk.Entry(form, width=20, style="App.TEntry")
        self.sku_entry.grid(row=2, column=1, sticky=tk.W, pady=4)

        self.quantity_entry = ttk.Entry(form, width=10, style="App.TEntry")
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(row=2, column=3, sticky=tk.W, pady=4)

        self.signed_check = ttk.Checkbutton(
            form, text="Signed by the author",
            variable=self.signed_var, style="Victorian.TCheckbutton")
        self.signed_check.grid(row=3, column=0, columnspan=2, sticky=tk.W,
                               padx=(0, 20), pady=(4, 6))

        self.special_check = ttk.Checkbutton(
            form, text="Special edition",
            variable=self.special_var, style="Victorian.TCheckbutton")
        self.special_check.grid(row=3, column=2, columnspan=2, sticky=tk.W, pady=(4, 6))

        self.button_row = tk.Frame(form)
        self.button_row.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))

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

        self.footer_label = tk.Label(tab, text="— EST 1997 —")
        self.footer_label.grid(row=5, column=0, pady=(0, 8))

    def _build_search_tab(self) -> None:
        tab = tk.Frame(self.notebook)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        self.notebook.add(tab, text="  Search  ")
        self._search_tab = tab

        # Search bar row
        search_bar = tk.Frame(tab)
        search_bar.grid(row=0, column=0, sticky=tk.EW, padx=16, pady=(16, 6))
        search_bar.columnconfigure(1, weight=1)
        self._search_bar = search_bar

        self._search_label = tk.Label(search_bar, text="Search")
        self._search_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        self.search_entry = ttk.Entry(search_bar, style="App.TEntry")
        self.search_entry.grid(row=0, column=1, sticky=tk.EW)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        self._search_clear_btn = tk.Button(
            search_bar, text="✕", command=self._clear_search,
            relief=tk.FLAT, bd=0, padx=6, cursor="hand2", highlightthickness=0)
        self._search_clear_btn.grid(row=0, column=2, padx=(6, 0))

        # Toggle view button
        self._view_toggle_btn = tk.Button(
            search_bar, text="⊞ Grid", command=self._toggle_search_view,
            relief=tk.FLAT, bd=0, padx=8, cursor="hand2", highlightthickness=0)
        self._view_toggle_btn.grid(row=0, column=3, padx=(6, 0))

        # Type filter row
        filter_row = tk.Frame(tab)
        filter_row.grid(row=1, column=0, sticky=tk.EW, padx=16, pady=(0, 6))
        self._filter_row = filter_row

        self._filter_label = tk.Label(filter_row, text="Filter by type:")
        self._filter_label.pack(side=tk.LEFT, padx=(0, 10))

        self._type_filter = tk.StringVar(value="All")
        self._filter_radios = []
        for label in ("All", TYPE_REGULAR, TYPE_SIGNED, TYPE_SPECIAL, TYPE_SIGNED_SPECIAL):
            rb = tk.Radiobutton(
                filter_row, text=label,
                variable=self._type_filter, value=label,
                command=self._run_search, highlightthickness=0, bd=0)
            rb.pack(side=tk.LEFT, padx=(0, 8))
            self._filter_radios.append(rb)

        # Results count
        self._results_label = tk.Label(tab, text="")
        self._results_label.grid(row=2, column=0, sticky=tk.E, padx=16, pady=(0, 4))

        # Results area — holds either table or grid
        self._results_area = tk.Frame(tab)
        self._results_area.grid(row=3, column=0, sticky=tk.NSEW, padx=16, pady=(0, 16))
        self._results_area.columnconfigure(0, weight=1)
        self._results_area.rowconfigure(0, weight=1)

        # Table view
        self._table_frame = tk.Frame(self._results_area)
        self._table_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self._table_frame.columnconfigure(0, weight=1)
        self._table_frame.rowconfigure(0, weight=1)

        self.search_tree = self._make_treeview(self._table_frame)
        self.search_tree.grid(row=0, column=0, sticky=tk.NSEW)
        scroll = ttk.Scrollbar(self._table_frame, orient=tk.VERTICAL,
                               command=self.search_tree.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.search_tree.configure(yscrollcommand=scroll.set)

        # Grid view — scrollable canvas
        self._grid_frame = tk.Frame(self._results_area)
        self._grid_frame.columnconfigure(0, weight=1)
        self._grid_frame.rowconfigure(0, weight=1)

        self._grid_canvas = tk.Canvas(self._grid_frame, highlightthickness=0, bd=0)
        self._grid_canvas.grid(row=0, column=0, sticky=tk.NSEW)

        grid_scroll = ttk.Scrollbar(self._grid_frame, orient=tk.VERTICAL,
                                    command=self._grid_canvas.yview)
        grid_scroll.grid(row=0, column=1, sticky=tk.NS)
        self._grid_canvas.configure(yscrollcommand=grid_scroll.set)

        self._grid_inner = tk.Frame(self._grid_canvas)
        self._grid_canvas_window = self._grid_canvas.create_window(
            (0, 0), window=self._grid_inner, anchor=tk.NW)

        self._grid_inner.bind("<Configure>", self._on_grid_configure)
        self._grid_canvas.bind("<Configure>", self._on_canvas_configure)
        self._grid_canvas.bind("<MouseWheel>", self._on_grid_scroll)

    def _make_treeview(self, parent: tk.Misc) -> ttk.Treeview:
        """Create a standard 6-column book treeview."""
        tree = ttk.Treeview(parent, columns=TREE_COLUMNS,
                            show="headings", height=10, style="App.Treeview")
        tree.heading("title",           text="Volume Title")
        tree.heading("author",          text="Author")
        tree.heading("quantity",        text="Copies")
        tree.heading("signed",          text="Signed")
        tree.heading("special_edition", text="Special Ed.")
        tree.heading("type",            text="Type")
        tree.column("title",           width=260, anchor=tk.W)
        tree.column("author",          width=200, anchor=tk.W)
        tree.column("quantity",        width=60,  anchor=tk.CENTER)
        tree.column("signed",          width=80,  anchor=tk.CENTER)
        tree.column("special_edition", width=90,  anchor=tk.CENTER)
        tree.column("type",            width=180, anchor=tk.W)
        return tree

    # ── View toggle ───────────────────────────────────────────────────────────

    def _toggle_search_view(self) -> None:
        """Switch between table and grid view in the search tab."""
        if self._search_view == "table":
            self._search_view = "grid"
            self._view_toggle_btn.configure(text="☰ Table")
            self._table_frame.grid_remove()
            self._grid_frame.grid(row=0, column=0, sticky=tk.NSEW)
        else:
            self._search_view = "table"
            self._view_toggle_btn.configure(text="⊞ Grid")
            self._grid_frame.grid_remove()
            self._table_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self._run_search()

    def _on_grid_configure(self, _event=None) -> None:
        self._grid_canvas.configure(
            scrollregion=self._grid_canvas.bbox("all"))

    def _on_canvas_configure(self, event=None) -> None:
        if event:
            self._grid_canvas.itemconfig(
                self._grid_canvas_window, width=event.width)

    def _on_grid_scroll(self, event: tk.Event) -> None:
        self._grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _populate_grid(self, books: list[dict]) -> None:
        """Render *books* as styled cover cards in the grid view."""
        c = self.theme.colors
        f = self.theme.fonts

        for widget in self._grid_inner.winfo_children():
            widget.destroy()

        self._grid_canvas.configure(bg=c.surface)
        self._grid_inner.configure(bg=c.surface)

        CARD_W = 160
        CARD_H = 220
        PAD    = 14
        COLS   = 5

        # Badge colors per type
        badge_colors = {
            TYPE_REGULAR:        (c.tag_regular_bg,        c.tag_regular_fg),
            TYPE_SIGNED:         (c.tag_signed_bg,         c.tag_signed_fg),
            TYPE_SPECIAL:        (c.tag_special_bg,        c.tag_special_fg),
            TYPE_SIGNED_SPECIAL: (c.tag_signed_special_bg, c.tag_signed_special_fg),
        }

        # A palette of cover spine colors — cycles through books
        spine_colors = [
            "#3b1f2b", "#1a2a4a", "#0f3020", "#2a1a40",
            "#3d1a0f", "#1a3a2a", "#2a0f3d", "#1f2b1a",
        ]

        for idx, book in enumerate(books):
            row = idx // COLS
            col = idx % COLS

            _, _, _, type_label = self._row_meta(
                book["signed"], book["special_edition"])
            badge_bg, badge_fg = badge_colors.get(
                type_label, (c.tag_regular_bg, c.tag_regular_fg))
            spine = spine_colors[idx % len(spine_colors)]

            # Card outer frame (acts as border)
            card_border = tk.Frame(
                self._grid_inner,
                bg=c.border, padx=1, pady=1,
                width=CARD_W, height=CARD_H)
            card_border.grid(row=row, column=col, padx=PAD, pady=PAD)
            card_border.grid_propagate(False)

            # Card inner
            card = tk.Frame(card_border, bg=spine,
                            width=CARD_W - 2, height=CARD_H - 2)
            card.pack(fill=tk.BOTH, expand=True)
            card.pack_propagate(False)

            # Spine stripe on left edge
            tk.Frame(card, bg=c.border, width=6).pack(side=tk.LEFT, fill=tk.Y)

            body = tk.Frame(card, bg=spine)
            body.pack(fill=tk.BOTH, expand=True, padx=8, pady=10)

            # Title
            tk.Label(body, text=book["title"],
                     font=(f.display, 11, "bold"),
                     fg=c.text, bg=spine,
                     wraplength=CARD_W - 40,
                     justify=tk.LEFT,
                     anchor=tk.NW).pack(anchor=tk.NW, pady=(0, 6))

            # Author
            author = book.get("author", "") or ""
            if author:
                tk.Label(body, text=author,
                         font=(f.body, 9, "italic"),
                         fg=c.text_muted, bg=spine,
                         wraplength=CARD_W - 40,
                         justify=tk.LEFT).pack(anchor=tk.NW, pady=(0, 8))

            # Qty badge at bottom
            qty_frame = tk.Frame(body, bg=spine)
            qty_frame.pack(side=tk.BOTTOM, anchor=tk.SW, pady=(4, 0))
            tk.Label(qty_frame,
                     text=f"×{book['quantity']}",
                     font=(f.body, 8),
                     fg=c.text_muted, bg=spine).pack(side=tk.LEFT)

            # Type badge
            badge_frame = tk.Frame(card, bg=badge_bg, padx=4, pady=2)
            badge_frame.place(relx=1.0, rely=1.0, anchor=tk.SE, x=-4, y=-4)
            tk.Label(badge_frame, text=type_label,
                     font=(f.body, 7, "bold"),
                     fg=badge_fg, bg=badge_bg).pack()

    # ── Browse overlay ────────────────────────────────────────────────────────

    def _open_browse_overlay(self) -> None:
        books = load_books()
        c = self.theme.colors
        f = self.theme.fonts

        overlay = tk.Toplevel(self.root)
        overlay.title(f"{APP_TITLE} — Full Collection")
        overlay.configure(bg=c.window_bg)
        overlay.state("zoomed")
        overlay.grab_set()

        header = tk.Frame(overlay, bg=c.surface, pady=12)
        header.pack(fill=tk.X, padx=24, pady=(16, 0))
        tk.Label(header, text="Full Collection",
                 font=f.title(), fg=c.accent, bg=c.surface).pack()
        n_titles = unique_titles(books)
        copies   = total_count(books)
        tk.Label(header,
                 text=f"{n_titles} titles  ·  {copies} total copies",
                 font=f.subtitle(), fg=c.text_muted, bg=c.surface).pack(pady=(2, 0))

        tk.Frame(overlay, bg=c.border, height=2).pack(fill=tk.X, padx=24, pady=(10, 0))

        search_frame = tk.Frame(overlay, bg=c.surface, pady=6)
        search_frame.pack(fill=tk.X, padx=24, pady=(6, 0))
        tk.Label(search_frame, text="Search:", font=f.label(),
                 fg=c.text, bg=c.surface).pack(side=tk.LEFT, padx=(0, 8))
        ov_search = ttk.Entry(search_frame, width=40, style="App.TEntry")
        ov_search.pack(side=tk.LEFT)

        tree_frame = tk.Frame(overlay, bg=c.window_bg)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=10)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        ov_tree = self._make_treeview(tree_frame)
        ov_tree.configure(height=30)
        ov_tree.grid(row=0, column=0, sticky=tk.NSEW)
        ov_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=ov_tree.yview)
        ov_scroll.grid(row=0, column=1, sticky=tk.NS)
        ov_tree.configure(yscrollcommand=ov_scroll.set)

        for tag, bg, fg in [
            ("signed_special", c.tag_signed_special_bg, c.tag_signed_special_fg),
            ("signed_only",    c.tag_signed_bg,         c.tag_signed_fg),
            ("special_only",   c.tag_special_bg,        c.tag_special_fg),
            ("regular",        c.tag_regular_bg,        c.tag_regular_fg),
        ]:
            ov_tree.tag_configure(tag, background=bg, foreground=fg, font=f.badge())

        def populate(subset: list[dict]) -> None:
            for item in ov_tree.get_children():
                ov_tree.delete(item)
            for book in subset:
                tag, st, spt, tl = self._row_meta(
                    book["signed"], book["special_edition"])
                ov_tree.insert("", tk.END, values=(
                    book["title"], book.get("author", ""),
                    book["quantity"], st, spt, tl), tags=(tag,))

        def on_ov_search(*_) -> None:
            q = ov_search.get().strip().casefold()
            populate([b for b in books if _book_matches(b, q, "All")] if q else books)

        ov_search.bind("<KeyRelease>", on_ov_search)
        populate(books)

        btn_frame = tk.Frame(overlay, bg=c.window_bg, pady=8)
        btn_frame.pack(fill=tk.X, padx=24)
        close_btn = self._make_button(btn_frame, "Close", overlay.destroy)
        close_btn.configure(bg=c.accent, fg=c.text_on_accent,
                            activebackground=c.accent_hi,
                            activeforeground=c.text_on_accent)
        close_btn.pack(side=tk.RIGHT)

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search_key(self, _event: tk.Event) -> None:
        if self._search_after_id:
            self.root.after_cancel(self._search_after_id)
        self._search_after_id = self.root.after(200, self._run_search)

    def _clear_search(self) -> None:
        self.search_entry.delete(0, tk.END)
        self._type_filter.set("All")
        self._run_search()

    def _run_search(self) -> None:
        query       = self.search_entry.get().strip().casefold()
        type_filter = self._type_filter.get()
        books       = load_books()
        results     = [b for b in books if _book_matches(b, query, type_filter)]

        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        for book in results:
            tag, st, spt, tl = self._row_meta(book["signed"], book["special_edition"])
            self.search_tree.insert("", tk.END, iid=str(book["id"]),
                values=(book["title"], book.get("author", ""),
                        book["quantity"], st, spt, tl), tags=(tag,))

        if self._search_view == "grid":
            self._populate_grid(results)

        count = len(results)
        self._results_label.config(
            text=f"{count} result{'s' if count != 1 else ''}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _on_title_suggestion(self, suggestion: dict) -> None:
        sku = suggestion.get("sku", "")
        if sku:
            self.sku_entry.delete(0, tk.END)
            self.sku_entry.insert(0, sku)
        author = suggestion.get("author", "")
        if author and not self.author_entry.get().strip():
            self.author_entry.delete(0, tk.END)
            self.author_entry.insert(0, author)

    def _make_button(self, master: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(master, text=text, command=command,
                         relief=tk.RAISED, bd=2, highlightthickness=0,
                         padx=12, pady=4, cursor="hand2")

    @staticmethod
    def _row_meta(signed: bool, special: bool) -> tuple[str, str, str, str]:
        if signed and special:
            return "signed_special", GLYPH_SIGNED, GLYPH_SPECIAL, TYPE_SIGNED_SPECIAL
        if signed:
            return "signed_only",    GLYPH_SIGNED, GLYPH_NONE,    TYPE_SIGNED
        if special:
            return "special_only",   GLYPH_NONE,   GLYPH_SPECIAL, TYPE_SPECIAL
        return     "regular",        GLYPH_NONE,   GLYPH_NONE,    TYPE_REGULAR

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        books = load_books()
        for book in books:
            tag, st, spt, tl = self._row_meta(book["signed"], book["special_edition"])
            self.tree.insert("", tk.END, iid=str(book["id"]),
                values=(book["title"], book.get("author", ""),
                        book["quantity"], st, spt, tl), tags=(tag,))

        n_titles = unique_titles(books)
        copies   = total_count(books)
        self.summary_label.config(
            text=(f"{n_titles} title{'s' if n_titles != 1 else ''}"
                  f"  ·  {copies} total cop{'ies' if copies != 1 else 'y'}"))
        self._run_search()

    def _parse_quantity(self) -> int:
        text = self.quantity_entry.get().strip()
        if not text:
            return 1
        if not text.isdigit() or int(text) < 1:
            raise ValueError(
                f'"{text}" is not a valid quantity. '
                "Please enter a whole number greater than zero.")
        return int(text)

    def _on_title_return(self, _event: tk.Event) -> str:
        self.on_add()
        return "break"

    def on_add(self) -> None:
        title  = self.title_entry.get_title()
        sku    = self.sku_entry.get().strip() or self.title_entry.get_sku() or None
        author = self.author_entry.get().strip() or None
        try:
            quantity = self._parse_quantity()
            add_book(title, quantity, sku=sku,
                     signed=self.signed_var.get(),
                     special_edition=self.special_var.get(),
                     author=author)
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
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Pray select a volume from the catalogue.")
            return

        item_id    = selected[0]
        values     = self.tree.item(item_id, "values")
        title      = values[0]
        quantity   = int(values[2])
        type_label = values[5]

        copy_word = "copy" if quantity == 1 else "copies"
        if not messagebox.askyesno("Remove Volume",
                f'Remove 1 of {quantity} {copy_word} of "{title}" ({type_label})?'):
            return

        try:
            remove_book(int(item_id))
        except ValueError as error:
            messagebox.showerror("Could Not Remove", str(error))
            return

        self.refresh_list()


# ── Search helper ─────────────────────────────────────────────────────────────

def _book_matches(book: dict, query: str, type_filter: str) -> bool:
    """Return True if *book* matches *query* (pre-lowercased) and *type_filter*."""
    if type_filter != "All":
        _, _, _, tl = BookInventoryApp._row_meta(
            book["signed"], book["special_edition"])
        if tl != type_filter:
            return False
    if not query:
        return True
    haystack = " ".join([
        book.get("title", ""),
        book.get("author", ""),
        book.get("sku", ""),
        BookInventoryApp._row_meta(book["signed"], book["special_edition"])[3],
    ]).casefold()
    return query in haystack


def main() -> None:
    root = tk.Tk()
    BookInventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()