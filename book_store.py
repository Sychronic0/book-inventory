from pathlib import Path

from database import get_connection, init_db, migrate_from_json

DATA_FILE = Path(__file__).parent / "books.json"


def _ensure_db() -> None:
    init_db()
    migrate_from_json(DATA_FILE)


def _normalize_sku(sku: str | None) -> str | None:
    if sku is None:
        return None
    sku = sku.strip()
    return sku or None


def load_books() -> list[dict]:
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, sku, quantity
            FROM library
            ORDER BY title COLLATE NOCASE
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "sku": row["sku"] or "",
            "quantity": row["quantity"],
        }
        for row in rows
    ]


def add_book(title: str, quantity: int = 1, sku: str | None = None) -> None:
    title = title.strip()
    sku = _normalize_sku(sku)
    if not title:
        raise ValueError("Title cannot be empty.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    _ensure_db()
    with get_connection() as connection:
        if sku:
            sku_row = connection.execute(
                "SELECT id, title FROM library WHERE sku = ?",
                (sku,),
            ).fetchone()
            if sku_row and sku_row["title"].casefold() != title.casefold():
                raise ValueError(f'SKU "{sku}" is already assigned to another volume.')

        row = connection.execute(
            "SELECT id, quantity, sku FROM library WHERE title = ? COLLATE NOCASE",
            (title,),
        ).fetchone()

        if row is None:
            connection.execute(
                "INSERT INTO library (title, sku, quantity) VALUES (?, ?, ?)",
                (title, sku, quantity),
            )
        else:
            connection.execute(
                "UPDATE library SET quantity = quantity + ? WHERE id = ?",
                (quantity, row["id"]),
            )
            if sku and not (row["sku"] or ""):
                connection.execute(
                    "UPDATE library SET sku = ? WHERE id = ?",
                    (sku, row["id"]),
                )


def remove_book(book_id: int) -> None:
    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM library WHERE id = ?",
            (book_id,),
        ).fetchone()
        if row is None:
            raise ValueError("That volume is no longer in your collection.")
        connection.execute("DELETE FROM library WHERE id = ?", (book_id,))


def total_count(books: list[dict]) -> int:
    return sum(book["quantity"] for book in books)
