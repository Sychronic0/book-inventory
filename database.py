"""SQLite layer for the book inventory.

Owns the schema for these tables:
  - library  : owned books with title, sku, quantity, edition flags,
                reading_status, notes, cover_url
  - wishlist : wanted books with title, author, notes
  - catalog  : cached search results from Open Library for offline use
  - prefs    : key-value store for app preferences

Schema migrations are additive ALTER TABLE ADD COLUMN (idempotent).
"""

import shutil
import sqlite3
import sys
from pathlib import Path


def app_dir() -> Path:
    """Folder the app's writable data files should live in.

    Frozen (PyInstaller) builds unpack into a temp folder that's wiped on
    exit, so __file__ can't be trusted there — anchor to the exe's real
    location instead. Running from source, __file__ is correct as-is.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


DB_FILE = app_dir() / "library.db"

READING_STATUSES = ("Unread", "Reading", "Finished", "DNF")
PREF_KEY_THEME   = "theme"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migrate_library_schema(connection: sqlite3.Connection) -> None:
    """Idempotently add any missing columns to the library table."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(library)")}
    additions = {
        "sku":            "ALTER TABLE library ADD COLUMN sku TEXT",
        "signed":         "ALTER TABLE library ADD COLUMN signed INTEGER NOT NULL DEFAULT 0",
        "special_edition":"ALTER TABLE library ADD COLUMN special_edition INTEGER NOT NULL DEFAULT 0",
        "author":         "ALTER TABLE library ADD COLUMN author TEXT",
        "reading_status": "ALTER TABLE library ADD COLUMN reading_status TEXT NOT NULL DEFAULT 'Unread'",
        "notes":          "ALTER TABLE library ADD COLUMN notes TEXT",
        "cover_url":      "ALTER TABLE library ADD COLUMN cover_url TEXT",
    }
    for col, sql in additions.items():
        if col not in columns:
            connection.execute(sql)


def _migrate_wishlist_schema(connection: sqlite3.Connection) -> None:
    """Idempotently add any missing columns to the wishlist table."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(wishlist)")}
    additions = {
        "author": "ALTER TABLE wishlist ADD COLUMN author TEXT",
        "notes":  "ALTER TABLE wishlist ADD COLUMN notes TEXT",
    }
    for col, sql in additions.items():
        if col not in columns:
            connection.execute(sql)


def _library_has_old_title_unique(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'library'"
    ).fetchone()
    if row is None or row["sql"] is None:
        return False
    sql_upper = row["sql"].upper()
    return "TITLE" in sql_upper and "UNIQUE" in sql_upper


def _rebuild_library_for_per_copy(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT id, title, sku, author, quantity, signed, special_edition FROM library"
    ).fetchall()

    connection.executescript("""
        CREATE TABLE library_new (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL COLLATE NOCASE,
            sku            TEXT,
            author         TEXT,
            quantity       INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            signed         INTEGER NOT NULL DEFAULT 0,
            special_edition INTEGER NOT NULL DEFAULT 0,
            reading_status TEXT NOT NULL DEFAULT 'Unread',
            notes          TEXT,
            cover_url      TEXT
        );
    """)

    for row in rows:
        title    = row["title"]
        sku      = row["sku"]
        author   = row["author"]
        signed   = int(row["signed"])
        special  = int(row["special_edition"])
        quantity = int(row["quantity"])

        if (signed or special) and quantity > 1:
            for index in range(quantity):
                copy_sku = sku if index == 0 else None
                connection.execute(
                    "INSERT INTO library_new (title, sku, author, quantity, signed, special_edition) "
                    "VALUES (?, ?, ?, 1, ?, ?)",
                    (title, copy_sku, author, signed, special),
                )
        else:
            connection.execute(
                "INSERT INTO library_new (title, sku, author, quantity, signed, special_edition) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, sku, author, quantity, signed, special),
            )

    connection.executescript("""
        DROP TABLE library;
        ALTER TABLE library_new RENAME TO library;
    """)


def init_db() -> None:
    if DB_FILE.exists():
        backup = DB_FILE.with_suffix(".db.migrating")
        shutil.copy2(DB_FILE, backup)

    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS library (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL COLLATE NOCASE,
                sku             TEXT,
                author          TEXT,
                quantity        INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                signed          INTEGER NOT NULL DEFAULT 0,
                special_edition INTEGER NOT NULL DEFAULT 0,
                reading_status  TEXT NOT NULL DEFAULT 'Unread',
                notes           TEXT,
                cover_url       TEXT
            );

            CREATE TABLE IF NOT EXISTS wishlist (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                title   TEXT NOT NULL COLLATE NOCASE,
                author  TEXT,
                notes   TEXT
            );

            CREATE TABLE IF NOT EXISTS catalog (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                title     TEXT NOT NULL,
                author    TEXT,
                source_id TEXT,
                UNIQUE(title, author)
            );

            CREATE INDEX IF NOT EXISTS idx_catalog_title
            ON catalog(title COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS prefs (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
        """)

        _migrate_library_schema(connection)
        _migrate_wishlist_schema(connection)

        connection.execute("DROP INDEX IF EXISTS idx_library_sku")
        connection.execute("DROP INDEX IF EXISTS idx_library_title_edition_sku")

        if _library_has_old_title_unique(connection):
            _rebuild_library_for_per_copy(connection)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_library_title_edition
            ON library(title COLLATE NOCASE, signed, special_edition);
        """)


def migrate_from_json(json_path: Path) -> None:
    if not json_path.exists():
        return
    import json
    with json_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list) or not data:
        return
    with get_connection() as connection:
        _migrate_library_schema(connection)
        existing = connection.execute("SELECT COUNT(*) AS count FROM library").fetchone()["count"]
        if existing:
            return
        for book in data:
            title    = str(book.get("title", "")).strip()
            quantity = int(book.get("quantity", 1))
            sku      = str(book.get("sku", "")).strip() or None
            if not title or quantity < 1:
                continue
            connection.execute(
                "INSERT OR IGNORE INTO library (title, sku, quantity) VALUES (?, ?, ?)",
                (title, sku, quantity),
            )


def get_pref(key: str, default: str = "") -> str:
    try:
        init_db()
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM prefs WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def set_pref(key: str, value: str) -> None:
    try:
        init_db()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO prefs(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
    except Exception:
        pass
