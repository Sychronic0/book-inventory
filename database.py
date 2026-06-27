"""SQLite layer for the book inventory.

Owns the schema for two tables:
  - library  : owned books with title, sku, quantity, edition flags
  - catalog  : cached search results from Open Library for offline use

Responsibilities:
  - init_db()              — create tables + indexes, run schema migrations
  - migrate_from_json()    — one-shot import of legacy books.json
  - get_connection()       — sqlite3 connection with Row factory + FK on

Schema migrations:
  - Additive ALTER TABLE ADD COLUMN for new flags (idempotent).
  - One-shot rebuild of the library table if it was created with the
    pre-per-copy schema (UNIQUE on title). The rebuild splits any flagged
    rows with quantity>1 into N rows of quantity=1, so each special
    copy becomes its own row.
  - SKU is a free-form annotation per row; no uniqueness constraint
    anywhere. The same SKU may appear on multiple rows (different
    editions of one title, or even multiple copies of one edition).
  - A non-unique index on (title, signed, special_edition) keeps the
    add_book() lookup fast.
"""

import shutil
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "library.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migrate_library_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(library)")}
    if "sku" not in columns:
        connection.execute("ALTER TABLE library ADD COLUMN sku TEXT")
    if "signed" not in columns:
        connection.execute(
            "ALTER TABLE library ADD COLUMN signed INTEGER NOT NULL DEFAULT 0"
        )
    if "special_edition" not in columns:
        connection.execute(
            "ALTER TABLE library ADD COLUMN special_edition INTEGER NOT NULL DEFAULT 0"
        )
    if "author" not in columns:
        connection.execute("ALTER TABLE library ADD COLUMN author TEXT")


def _library_has_old_title_unique(connection: sqlite3.Connection) -> bool:
    """True if the library table still carries the pre-per-copy UNIQUE(title)."""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'library'"
    ).fetchone()
    if row is None or row["sql"] is None:
        return False
    # Crude but reliable for the two shapes we care about: a CREATE TABLE
    # statement that contains "TITLE" + "UNIQUE" in the same column decl.
    sql_upper = row["sql"].upper()
    return "TITLE" in sql_upper and "UNIQUE" in sql_upper


def _rebuild_library_for_per_copy(connection: sqlite3.Connection) -> None:
    """Migrate the library table to the per-copy schema.

    Drops UNIQUE on title, then splits any row where signed=1 or
    special_edition=1 with quantity>1 into N rows of quantity=1. Plain
    rows are copied through unchanged. Wrapped in a single transaction
    so a failure rolls back atomically.
    """
    rows = connection.execute(
        "SELECT id, title, sku, author, quantity, signed, special_edition FROM library"
    ).fetchall()

    connection.executescript(
        """
        CREATE TABLE library_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL COLLATE NOCASE,
            sku TEXT,
            author TEXT,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            signed INTEGER NOT NULL DEFAULT 0,
            special_edition INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    for row in rows:
        title = row["title"]
        sku = row["sku"]
        author = row["author"]
        signed = int(row["signed"])
        special = int(row["special_edition"])
        quantity = int(row["quantity"])

        # Split flagged rows so each special copy is its own row.
        # Keep the SKU on the first copy only — the SKU identifies the
        # work/printing, not the individual physical copy, so subsequent
        # copies of the same edition share the same key and would collide
        # on the unique index. Users can still set distinct per-copy SKUs
        # later via the edit flow.
        if (signed or special) and quantity > 1:
            for index in range(quantity):
                copy_sku = sku if index == 0 else None
                connection.execute(
                    """
                    INSERT INTO library_new (title, sku, author, quantity, signed, special_edition)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (title, copy_sku, author, signed, special),
                )
        else:
            connection.execute(
                """
                INSERT INTO library_new (title, sku, author, quantity, signed, special_edition)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, sku, author, quantity, signed, special),
            )

    connection.executescript(
        """
        DROP TABLE library;
        ALTER TABLE library_new RENAME TO library;
        """
    )


def init_db() -> None:
    # Back up before any destructive migration so a failure leaves the
    # user's library recoverable. Backup is overwritten on each run.
    if DB_FILE.exists():
        backup = DB_FILE.with_suffix(".db.migrating")
        shutil.copy2(DB_FILE, backup)

    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL COLLATE NOCASE,
                sku TEXT,
                author TEXT,
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                signed INTEGER NOT NULL DEFAULT 0,
                special_edition INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                source_id TEXT,
                UNIQUE(title, author)
            );

            CREATE INDEX IF NOT EXISTS idx_catalog_title
            ON catalog(title COLLATE NOCASE);
            """
        )
        _migrate_library_schema(connection)

        # Drop the old global-unique SKU index if it exists from a prior
        # schema. Safe even if it doesn't exist.
        connection.execute("DROP INDEX IF EXISTS idx_library_sku")
        # Drop the per-(title + edition + sku) uniqueness index from a
        # prior schema. SKU is now a free-form annotation per row; the
        # same SKU may appear on any number of rows, including multiple
        # within one (title + edition).
        connection.execute("DROP INDEX IF EXISTS idx_library_title_edition_sku")

        if _library_has_old_title_unique(connection):
            _rebuild_library_for_per_copy(connection)

        # Non-unique index speeds up title lookups in add_book().
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_library_title_edition
            ON library(title COLLATE NOCASE, signed, special_edition);
            """
        )


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
            title = str(book.get("title", "")).strip()
            quantity = int(book.get("quantity", 1))
            sku = str(book.get("sku", "")).strip() or None
            if not title or quantity < 1:
                continue
            connection.execute(
                "INSERT OR IGNORE INTO library (title, sku, quantity) VALUES (?, ?, ?)",
                (title, sku, quantity),
            )