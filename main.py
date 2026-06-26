import tkinter as tk
from tkinter import messagebox, ttk

from book_store import add_book, load_books, remove_book, total_count
from autocomplete import AutocompleteEntry

APP_TITLE = "Samantha's Book Library"

# Victorian palette
MAHOGANY = "#2b1810"
BURGUNDY = "#5c2a2e"
CREAM = "#f5e6c8"
PARCHMENT = "#faf0dc"
GOLD = "#c9a227"
GOLD_LIGHT = "#e8c547"
INK = "#2a1a12"
BRASS = "#8b6914"

# Badge palette — soft jewel tones that read on parchment
SIGNED_FG = "#f5e6c8"        # cream text
SIGNED_BG = "#5c2a2e"        # burgundy pill
EDITION_FG = "#2a1a12"       # ink text
EDITION_BG = "#e8c547"       # gold pill
BADGES_PLAIN = "—"

# Glyphs used in the edition column (text-only badges inside the tree)
GLYPH_SIGNED = "✦ Signed"
GLYPH_SPECIAL = "❖ Special Edition"
GLYPH_BOTH = "✦ Signed  ❖ Special Edition"


class VictorianFrame(tk.Frame):
    """Double-bordered panel with a gold trim and parchment interior."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=GOLD, padx=2, pady=2, **kwargs)
        self.inner = tk.Frame(self, bg=PARCHMENT, padx=14, pady=14)
        self.inner.pack(fill=tk.BOTH, expand=True)


class BookInventoryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x720")
        self.root.minsize(720, 580)
        self.root.configure(bg=MAHOGANY)

        self.title_font = ("Georgia", 22, "bold")
        self.subtitle_font = ("Georgia", 11, "italic")
        self.body_font = ("Georgia", 11)
        self.label_font = ("Georgia", 10, "bold")
        self.button_font = ("Georgia", 10, "bold")
        self.badge_font = ("Georgia", 10, "bold")

        # Tk variables backing the edition checkboxes
        self.signed_var = tk.BooleanVar(value=False)
        self.special_var = tk.BooleanVar(value=False)

        self._configure_styles()
        self._build_ui()
        self.refresh_list()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Victorian.Treeview",
            background=PARCHMENT,
            foreground=INK,
            fieldbackground=PARCHMENT,
            bordercolor=GOLD,
            lightcolor=GOLD,
            darkcolor=BURGUNDY,
            rowheight=30,
            font=self.body_font,
        )
        style.configure(
            "Victorian.Treeview.Heading",
            background=BURGUNDY,
            foreground=CREAM,
            relief="flat",
            font=("Georgia", 11, "bold"),
        )
        style.map(
            "Victorian.Treeview",
            background=[("selected", BRASS)],
            foreground=[("selected", CREAM)],
        )
        style.configure(
            "Victorian.TEntry",
            fieldbackground=CREAM,
            foreground=INK,
            insertcolor=INK,
            bordercolor=GOLD,
            lightcolor=GOLD,
            padding=6,
        )
        style.configure(
            "Victorian.TCheckbutton",
            background=PARCHMENT,
            foreground=INK,
            font=self.body_font,
            focuscolor=GOLD,
        )
        style.map(
            "Victorian.TCheckbutton",
            background=[("active", PARCHMENT)],
            indicatorcolor=[("selected", BURGUNDY), ("!selected", CREAM)],
        )

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=MAHOGANY, padx=20, pady=20)
        outer.pack(fill=tk.BOTH, expand=True)

        shell = VictorianFrame(outer)
        shell.pack(fill=tk.BOTH, expand=True)
        main = shell.inner
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        header = tk.Frame(main, bg=PARCHMENT)
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 6))

        tk.Label(
            header,
            text=APP_TITLE,
            font=self.title_font,
            fg=BURGUNDY,
            bg=PARCHMENT,
        ).pack()

        tk.Label(
            header,
            text="❦   I HOPE YOU LIKE THIS <3   ❦",
            font=self.subtitle_font,
            fg=BRASS,
            bg=PARCHMENT,
        ).pack(pady=(4, 0))

        tk.Frame(main, bg=GOLD, height=2).grid(row=1, column=0, sticky=tk.EW, pady=(10, 12))

        summary_row = tk.Frame(main, bg=PARCHMENT)
        summary_row.grid(row=2, column=0, sticky=tk.EW, pady=(0, 10))

        tk.Label(
            summary_row,
            text="Collection at a glance",
            font=self.label_font,
            fg=INK,
            bg=PARCHMENT,
        ).pack(side=tk.LEFT)

        self.summary_label = tk.Label(
            summary_row,
            text="",
            font=self.subtitle_font,
            fg=BURGUNDY,
            bg=PARCHMENT,
        )
        self.summary_label.pack(side=tk.RIGHT)

        list_panel = VictorianFrame(main)
        list_panel.grid(row=3, column=0, sticky=tk.NSEW, pady=(0, 12))

        columns = ("title", "sku", "quantity", "edition")
        self.tree = ttk.Treeview(
            list_panel.inner,
            columns=columns,
            show="headings",
            height=8,
            style="Victorian.Treeview",
        )
        self.tree.heading("title", text="Volume Title")
        self.tree.heading("sku", text="SKU")
        self.tree.heading("quantity", text="Copies")
        self.tree.heading("edition", text="Edition")
        self.tree.column("title", width=300, anchor=tk.W)
        self.tree.column("sku", width=140, anchor=tk.W)
        self.tree.column("quantity", width=70, anchor=tk.CENTER)
        self.tree.column("edition", width=300, anchor=tk.W)

        # Row tags drive badge colors via the Treeview tag styling
        self.tree.tag_configure(
            "both",
            background=EDITION_BG,
            foreground=EDITION_FG,
            font=self.badge_font,
        )
        self.tree.tag_configure(
            "signed_only",
            background=SIGNED_BG,
            foreground=SIGNED_FG,
            font=self.badge_font,
        )
        self.tree.tag_configure(
            "special_only",
            background=EDITION_BG,
            foreground=EDITION_FG,
            font=self.badge_font,
        )
        self.tree.tag_configure(
            "plain",
            background=PARCHMENT,
            foreground=INK,
        )

        self.tree.pack(fill=tk.BOTH, expand=True)

        form_outer = tk.Frame(main, bg=PARCHMENT)
        form_outer.grid(row=4, column=0, sticky=tk.EW)

        tk.Label(
            form_outer,
            text="Register a Volume",
            font=self.label_font,
            fg=BURGUNDY,
            bg=PARCHMENT,
        ).pack(anchor=tk.W, pady=(0, 8))

        form_panel = VictorianFrame(form_outer)
        form_panel.pack(fill=tk.X)
        form = form_panel.inner

        tk.Label(form, text="Title", font=self.body_font, fg=INK, bg=PARCHMENT).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )
        self.title_entry = AutocompleteEntry(
            form,
            width=42,
            style="Victorian.TEntry",
            on_select=self._on_title_suggestion,
        )
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=6)

        tk.Label(form, text="SKU", font=self.body_font, fg=INK, bg=PARCHMENT).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )
        self.sku_entry = ttk.Entry(form, width=20, style="Victorian.TEntry")
        self.sku_entry.grid(row=1, column=1, sticky=tk.W, pady=6)

        tk.Label(form, text="Quantity", font=self.body_font, fg=INK, bg=PARCHMENT).grid(
            row=1, column=2, sticky=tk.W, padx=(20, 10), pady=6
        )
        self.quantity_entry = ttk.Entry(form, width=10, style="Victorian.TEntry")
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(row=1, column=3, sticky=tk.W, pady=6)

        # Edition flags — checkboxes styled to match the palette
        self.signed_check = ttk.Checkbutton(
            form,
            text="Signed by the author",
            variable=self.signed_var,
            style="Victorian.TCheckbutton",
        )
        self.signed_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=(0, 20), pady=(4, 8))

        self.special_check = ttk.Checkbutton(
            form,
            text="Special edition",
            variable=self.special_var,
            style="Victorian.TCheckbutton",
        )
        self.special_check.grid(row=2, column=2, columnspan=2, sticky=tk.W, padx=(0, 0), pady=(4, 8))

        buttons = tk.Frame(form, bg=PARCHMENT)
        buttons.grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=(10, 0))

        self._make_button(buttons, "Add to Library", self.on_add).pack(side=tk.LEFT, padx=(0, 10))
        self._make_button(buttons, "Remove Selected", self.on_remove).pack(side=tk.LEFT)

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.title_entry.bind("<Return>", self._on_title_return)
        self.sku_entry.bind("<Return>", lambda _event: self.on_add())
        self.quantity_entry.bind("<Return>", lambda _event: self.on_add())

        tk.Label(
            main,
            text="— EST 1997 —",
            font=("Georgia", 9, "italic"),
            fg=BRASS,
            bg=PARCHMENT,
        ).grid(row=5, column=0, pady=(14, 0))

    def _on_title_suggestion(self, suggestion: dict) -> None:
        sku = suggestion.get("sku", "")
        if sku:
            self.sku_entry.delete(0, tk.END)
            self.sku_entry.insert(0, sku)

    def _make_button(self, master: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            font=self.button_font,
            fg=CREAM,
            bg=BURGUNDY,
            activeforeground=CREAM,
            activebackground=BRASS,
            relief=tk.RAISED,
            bd=2,
            highlightbackground=GOLD,
            highlightcolor=GOLD_LIGHT,
            highlightthickness=1,
            padx=12,
            pady=4,
            cursor="hand2",
        )

    @staticmethod
    def _badge_for(signed: bool, special: bool) -> tuple[str, str]:
        """Return (tag, display_text) for the edition column."""
        if signed and special:
            return "both", GLYPH_BOTH
        if signed:
            return "signed_only", GLYPH_SIGNED
        if special:
            return "special_only", GLYPH_SPECIAL
        return "plain", BADGES_PLAIN

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        books = load_books()
        for book in sorted(books, key=lambda b: b["title"].casefold()):
            tag, badge_text = self._badge_for(
                book["signed"], book["special_edition"]
            )
            self.tree.insert(
                "",
                tk.END,
                iid=str(book["id"]),
                values=(
                    book["title"],
                    book["sku"],
                    book["quantity"],
                    badge_text,
                ),
                tags=(tag,),
            )

        unique = len(books)
        copies = total_count(books)
        self.summary_label.config(
            text=f"{unique} title{'s' if unique != 1 else ''}  ·  {copies} total cop{'ies' if copies != 1 else 'y'}"
        )

    def _parse_quantity(self) -> int:
        text = self.quantity_entry.get().strip()
        if not text:
            return 1
        return int(text)

    def _on_title_return(self, _event: tk.Event) -> str:
        self.on_add()
        return "break"

    def on_add(self) -> None:
        title = self.title_entry.get_title()
        sku = self.sku_entry.get().strip() or self.title_entry.get_sku() or None
        try:
            quantity = self._parse_quantity()
            add_book(
                title,
                quantity,
                sku=sku,
                signed=self.signed_var.get(),
                special_edition=self.special_var.get(),
            )
        except ValueError as error:
            messagebox.showerror("Invalid Entry", str(error))
            return

        self.title_entry.clear()
        self.sku_entry.delete(0, tk.END)
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

        item_id = selected[0]
        values = self.tree.item(item_id, "values")
        title = values[0]
        if not messagebox.askyesno("Remove Volume", f'Remove all copies of "{title}" from the library?'):
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
