"""Theme system for the Book Inventory UI.

Two themes:
  VICTORIAN — warm parchment, mahogany, burgundy, gold
  FOREST    — body-rot horror: near-black violet, bruise-purple,
              dark moss green, bone text

Usage:
    VICTORIAN_THEME, FOREST_THEME = build_themes(display_family, body_family)
    ThemeManager(app).apply(VICTORIAN_THEME)
"""

from __future__ import annotations
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class Colors:
    window_bg: str
    surface: str
    surface_alt: str
    border: str
    border_hi: str
    text: str
    text_muted: str
    text_on_accent: str
    accent: str
    accent_hi: str
    gold: str
    tag_signed_bg: str
    tag_signed_fg: str
    tag_special_bg: str
    tag_special_fg: str
    tag_signed_special_bg: str
    tag_signed_special_fg: str
    tag_regular_bg: str
    tag_regular_fg: str
    tag_selected_bg: str
    tag_selected_fg: str
    entry_bg: str
    popup_bg: str
    popup_select_bg: str
    popup_select_fg: str


@dataclass(frozen=True)
class Fonts:
    display: str
    body: str

    def title(self)    -> tuple: return (self.display, 22, "bold")
    def subtitle(self) -> tuple: return (self.body,    11, "italic")
    def body_f(self)   -> tuple: return (self.body,    11)
    def label(self)    -> tuple: return (self.body,    10, "bold")
    def button(self)   -> tuple: return (self.body,    10, "bold")
    def badge(self)    -> tuple: return (self.body,    10, "bold")
    def footer(self)   -> tuple: return (self.body,     9, "italic")
    def heading(self)  -> tuple: return (self.display, 11, "bold")


@dataclass(frozen=True)
class Theme:
    name: str
    colors: Colors
    fonts: Fonts


def _make_victorian(display: str, body: str) -> Theme:
    c = Colors(
        window_bg="#2b1810",
        surface="#faf0dc",
        surface_alt="#f5e6c8",
        border="#c9a227",
        border_hi="#e8c547",
        text="#2a1a12",
        text_muted="#8b6914",
        text_on_accent="#f5e6c8",
        accent="#5c2a2e",
        accent_hi="#8b6914",
        gold="#c9a227",
        tag_signed_bg="#5c2a2e",
        tag_signed_fg="#f5e6c8",
        tag_special_bg="#e8c547",
        tag_special_fg="#2a1a12",
        tag_signed_special_bg="#e8c547",
        tag_signed_special_fg="#2a1a12",
        tag_regular_bg="#faf0dc",
        tag_regular_fg="#2a1a12",
        tag_selected_bg="#8b6914",
        tag_selected_fg="#f5e6c8",
        entry_bg="#f5e6c8",
        popup_bg="#faf0dc",
        popup_select_bg="#8b6914",
        popup_select_fg="#f5e6c8",
    )
    return Theme(name="Victorian", colors=c, fonts=Fonts(display=display, body=body))


def _make_forest(display: str, body: str) -> Theme:
    c = Colors(
        window_bg="#0d0a14",
        surface="#15101f",
        surface_alt="#1a1426",
        border="#2a1f3a",
        border_hi="#4a2d6b",
        text="#f0ead6",
        text_muted="#8a7a9c",
        text_on_accent="#f0ead6",
        accent="#4a2d6b",
        accent_hi="#6b3d8a",
        gold="#2a1f3a",
        tag_signed_bg="#1a3d08",        # deep dark moss
        tag_signed_fg="#a8d878",        # sickly lime text
        tag_special_bg="#4a2d6b",       # bruise-purple
        tag_special_fg="#f0ead6",
        tag_signed_special_bg="#0f2405",
        tag_signed_special_fg="#a8d878",
        tag_regular_bg="#15101f",
        tag_regular_fg="#f0ead6",
        tag_selected_bg="#6b3d8a",
        tag_selected_fg="#f0ead6",
        entry_bg="#1a1426",
        popup_bg="#15101f",
        popup_select_bg="#4a2d6b",
        popup_select_fg="#f0ead6",
    )
    return Theme(name="Forest", colors=c, fonts=Fonts(display=display, body=body))


def build_themes(display: str, body: str) -> tuple[Theme, Theme]:
    return _make_victorian(display, body), _make_forest(display, body)


class ThemeManager:
    """Restyles a BookInventoryApp instance to a new Theme live."""

    def __init__(self, app) -> None:
        self._app = app

    def apply(self, theme: Theme) -> None:
        app = self._app
        c = theme.colors
        f = theme.fonts

        # Root + outer padding
        app.root.configure(bg=c.window_bg)
        app.outer.configure(bg=c.window_bg)

        # Shell border + inner
        app.shell.configure(bg=c.border)
        app.shell.inner.configure(bg=c.window_bg)

        # ── Library tab ──────────────────────────────────────────────────────
        app._library_tab.configure(bg=c.surface)

        app.header_frame.configure(bg=c.surface)
        app.title_label.configure(fg=c.accent, bg=c.surface, font=f.title())
        app.subtitle_label.configure(fg=c.text_muted, bg=c.surface, font=f.subtitle())
        app.divider.configure(bg=c.gold)

        app.summary_row.configure(bg=c.surface)
        app.summary_header.configure(fg=c.text, bg=c.surface, font=f.label())
        app.summary_label.configure(fg=c.accent, bg=c.surface, font=f.subtitle())
        app.browse_btn.configure(
            fg=c.accent, bg=c.surface,
            activeforeground=c.accent_hi, activebackground=c.surface,
            font=f.label())

        app.form_outer.configure(bg=c.surface)
        app.form_heading.configure(fg=c.accent, bg=c.surface, font=f.label())
        app.form_panel_shell.configure(bg=c.border)
        app.form_panel_shell.inner.configure(bg=c.surface)

        for lbl in app.form_labels:
            lbl.configure(fg=c.text, bg=c.surface, font=f.body_f())

        app.signed_check.configure(style=f"{theme.name}.TCheckbutton")
        app.special_check.configure(style=f"{theme.name}.TCheckbutton")
        app.button_row.configure(bg=c.surface)

        for btn in app.action_buttons:
            btn.configure(
                fg=c.text_on_accent, bg=c.accent,
                activeforeground=c.text_on_accent, activebackground=c.accent_hi,
                highlightbackground=c.border, font=f.button())

        app.footer_label.configure(fg=c.text_muted, bg=c.surface, font=f.footer())

        # ── Search tab ───────────────────────────────────────────────────────
        app._search_tab.configure(bg=c.surface)
        app._search_bar.configure(bg=c.surface)
        app._filter_row.configure(bg=c.surface)
        app._search_label.configure(fg=c.text, bg=c.surface, font=f.label())
        app._search_clear_btn.configure(
            fg=c.text_muted, bg=c.surface,
            activeforeground=c.text, activebackground=c.surface)
        app._view_toggle_btn.configure(
            fg=c.accent, bg=c.surface,
            activeforeground=c.accent_hi, activebackground=c.surface,
            font=f.label())
        app._results_label.configure(fg=c.text_muted, bg=c.surface, font=f.subtitle())
        app._filter_label.configure(fg=c.text, bg=c.surface, font=f.label())

        for rb in app._filter_radios:
            rb.configure(
                fg=c.text, bg=c.surface,
                activeforeground=c.text, activebackground=c.surface,
                selectcolor=c.surface,
                font=f.body_f())

        # Restyle both notebook tabs' bg
        for tab_id in app.notebook.tabs():
            w = app.notebook.nametowidget(tab_id)
            w.configure(bg=c.surface)

        # Rebuild ttk styles + treeview tags
        app.theme = theme
        app._configure_styles()

        # Autocomplete popup
        if hasattr(app.title_entry, "set_theme_provider"):
            app.title_entry.set_theme_provider(lambda: {
                "bg": c.popup_bg, "fg": c.text,
                "select_bg": c.popup_select_bg, "select_fg": c.popup_select_fg,
                "border": c.border, "border_hi": c.border_hi,
                "scrollbar_bg": c.surface_alt, "scrollbar_active": c.accent_hi,
            })