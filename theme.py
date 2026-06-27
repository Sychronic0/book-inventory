"""Theme system for the Book Inventory UI.

Provides two themes:
  - VICTORIAN_THEME  — warm parchment, mahogany, burgundy, gold
  - FOREST_THEME     — body-rot horror: near-black violet, bruise-purple,
                       sickly moss, bone text

Usage
-----
    from theme import VICTORIAN_THEME, FOREST_THEME, ThemeManager

    # At startup, pick a theme and apply it:
    manager = ThemeManager(app)
    manager.apply(VICTORIAN_THEME)

    # To switch live:
    manager.apply(FOREST_THEME)

ThemeManager.apply() walks every widget reference stored on the app,
restyles ttk styles, and calls _configure_styles() on the app so that
Treeview tags and ttk style maps are rebuilt with the new palette.

The app must expose these attributes for ThemeManager to restyle them:
    root, title_label, subtitle_label, header_frame, divider,
    summary_row, summary_header, summary_label, form_outer,
    form_heading, form_labels (list), button_row, footer_label,
    action_buttons (list), signed_check, special_check,
    title_entry, form_panel_shell (VictorianFrame),
    list_panel_shell (VictorianFrame), shell (VictorianFrame)
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Colors:
    """All palette values for one theme."""

    # Backgrounds
    window_bg: str       # outermost root window
    surface: str         # main parchment / surface
    surface_alt: str     # slightly different inner panels
    border: str          # frame borders / dividers
    border_hi: str       # highlighted border

    # Text
    text: str            # primary body text
    text_muted: str      # subtitles, secondary labels
    text_on_accent: str  # text placed on accent backgrounds

    # Accents
    accent: str          # primary accent (headings, buttons)
    accent_hi: str       # hover / active accent
    gold: str            # decorative gold / divider color

    # Treeview row tags
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

    # Entry / autocomplete popup
    entry_bg: str
    popup_bg: str
    popup_select_bg: str
    popup_select_fg: str


@dataclass(frozen=True)
class Fonts:
    """Font tuples for one theme."""

    display: str   # resolved display family (Cinzel etc.)
    body: str      # resolved body family (Georgia etc.)

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
    """A complete visual theme — colors + fonts + display name."""

    name: str
    colors: Colors
    fonts: Fonts


# ── Victorian ────────────────────────────────────────────────────────────────

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


# ── Forest (body-rot horror) ─────────────────────────────────────────────────

def _make_forest(display: str, body: str) -> Theme:
    c = Colors(
        window_bg="#0d0a14",
        surface="#15101f",
        surface_alt="#1a1426",
        border="#2a1f3a",
        border_hi="#4a2d6b",
        text="#f0ead6",          # bone — never pure white
        text_muted="#8a7a9c",
        text_on_accent="#f0ead6",
        accent="#4a2d6b",        # bruise-purple
        accent_hi="#6b3d8a",
        gold="#4a2d6b",          # reuse accent as "gold" divider
        tag_signed_bg="#6b8e23",       # sickly moss
        tag_signed_fg="#0d0a14",
        tag_special_bg="#4a2d6b",      # bruise-purple
        tag_special_fg="#f0ead6",
        tag_signed_special_bg="#3d1f5c",
        tag_signed_special_fg="#f0ead6",
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
    """Construct both themes using the resolved font families."""
    return _make_victorian(display, body), _make_forest(display, body)


# ── ThemeManager ─────────────────────────────────────────────────────────────

class ThemeManager:
    """Restyles a BookInventoryApp instance to a new Theme live."""

    def __init__(self, app) -> None:
        self._app = app

    def apply(self, theme: Theme) -> None:
        """Apply *theme* to every widget the app exposes."""
        app = self._app
        c = theme.colors
        f = theme.fonts

        # Root window and outer padding frame
        app.root.configure(bg=c.window_bg)
        app.outer.configure(bg=c.window_bg)

        # Outer shell VictorianFrame border + inner surface
        app.shell.configure(bg=c.border)
        app.shell.inner.configure(bg=c.surface)

        # Header
        app.header_frame.configure(bg=c.surface)
        app.title_label.configure(fg=c.accent, bg=c.surface, font=f.title())
        app.subtitle_label.configure(fg=c.text_muted, bg=c.surface, font=f.subtitle())

        # Divider
        app.divider.configure(bg=c.gold)

        # Summary row
        app.summary_row.configure(bg=c.surface)
        app.summary_header.configure(fg=c.text, bg=c.surface, font=f.label())
        app.summary_label.configure(fg=c.accent, bg=c.surface, font=f.subtitle())

        # List panel shell
        app.list_panel_shell.configure(bg=c.border)
        app.list_panel_shell.inner.configure(bg=c.surface)

        # Form outer
        app.form_outer.configure(bg=c.surface)
        app.form_heading.configure(fg=c.accent, bg=c.surface, font=f.label())

        # Form panel shell
        app.form_panel_shell.configure(bg=c.border)
        app.form_panel_shell.inner.configure(bg=c.surface)

        # Form labels
        for lbl in app.form_labels:
            lbl.configure(fg=c.text, bg=c.surface, font=f.body_f())

        # Checkbuttons
        app.signed_check.configure(style=f"{theme.name}.TCheckbutton")
        app.special_check.configure(style=f"{theme.name}.TCheckbutton")

        # Button row frame
        app.button_row.configure(bg=c.surface)

        # Action buttons
        for btn in app.action_buttons:
            btn.configure(
                fg=c.text_on_accent,
                bg=c.accent,
                activeforeground=c.text_on_accent,
                activebackground=c.accent_hi,
                highlightbackground=c.border,
                highlightcolor=c.border_hi,
                font=f.button(),
            )

        # Footer
        app.footer_label.configure(fg=c.text_muted, bg=c.surface, font=f.footer())

        # Rebuild ttk styles + treeview tags with new palette
        app.theme = theme
        app._configure_styles()

        # Update autocomplete popup colors if supported
        if hasattr(app.title_entry, "set_theme_provider"):
            app.title_entry.set_theme_provider(lambda: {
                "bg": c.popup_bg,
                "fg": c.text,
                "select_bg": c.popup_select_bg,
                "select_fg": c.popup_select_fg,
                "border": c.border,
                "border_hi": c.border_hi,
                "scrollbar_bg": c.surface_alt,
                "scrollbar_active": c.accent_hi,
            })