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


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL COLLATE NOCASE UNIQUE,
                sku TEXT,
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
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_library_sku
            ON library(sku)
            WHERE sku IS NOT NULL AND sku != '';
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
