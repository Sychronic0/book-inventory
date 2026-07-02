"""Book storage layer — CRUD against the local SQLite inventory database.

Covers: library (owned books) and wishlist (wanted books).

Inventory model:
  - Each row in `library` represents a distinct edition of a title
    (title, signed, special_edition). Adding with the same flags
    increments quantity; different flags create a new row.
  - remove_book() decrements quantity; deletes row at zero.
  - edit_book() updates any field on a row by id.
  - Wishlist is a separate table — simpler, no editions or quantity.
"""

from pathlib import Path

from database import (
    READING_STATUSES, get_connection, init_db, migrate_from_json
)

DATA_FILE = Path(__file__).parent / "books.json"

_EDITION_ORDER = {
    (False, False): 0,
    (True,  False): 1,
    (False, True):  2,
    (True,  True):  3,
}


def _ensure_db() -> None:
    """Initialize the database and run any pending migrations."""
    init_db()
    migrate_from_json(DATA_FILE)


def _normalize_sku(sku: str | None) -> str | None:
    """Strip whitespace from *sku* and return None if the result is empty."""
    if sku is None:
        return None
    sku = sku.strip()
    return sku or None


def _row_to_dict(row) -> dict:
    """Convert a library sqlite3.Row to a plain dict."""
    return {
        "id":             row["id"],
        "title":          row["title"],
        "sku":            row["sku"] or "",
        "author":         row["author"] or "",
        "quantity":       row["quantity"],
        "signed":         bool(row["signed"]),
        "special_edition":bool(row["special_edition"]),
        "reading_status": row["reading_status"] or "Unread",
        "notes":          row["notes"] or "",
        "cover_url":      row["cover_url"] or "",
    }


# ── Library ───────────────────────────────────────────────────────────────────

def load_books() -> list[dict]:
    """Return all books grouped by title (A→Z) then edition type."""
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, sku, author, quantity, signed, special_edition, "
            "reading_status, notes, cover_url FROM library"
        ).fetchall()

    books = [_row_to_dict(row) for row in rows]
    books.sort(key=lambda b: (
        b["title"].casefold(),
        _EDITION_ORDER[(b["signed"], b["special_edition"])],
    ))
    return books


def unique_titles(books: list[dict]) -> int:
    """Return the number of distinct titles with quantity > 0."""
    return len({book["title"].casefold() for book in books if book["quantity"] > 0})


def total_count(books: list[dict]) -> int:
    """Return the total number of copies across all books."""
    return sum(book["quantity"] for book in books)


def add_book(
    title: str,
    quantity: int = 1,
    sku: str | None = None,
    signed: bool = False,
    special_edition: bool = False,
    author: str | None = None,
    reading_status: str = "Unread",
    notes: str | None = None,
) -> None:
    """Add *quantity* copies of *title* to the inventory."""
    title = title.strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")
    if reading_status not in READING_STATUSES:
        reading_status = "Unread"
    sku    = _normalize_sku(sku)
    author = (author or "").strip() or None
    notes  = (notes or "").strip() or None

    new_signed = int(bool(signed))
    new_special = int(bool(special_edition))

    _ensure_db()
    with get_connection() as connection:
        try:
            row = connection.execute(
                "SELECT id, quantity, sku, author FROM library "
                "WHERE title = ? COLLATE NOCASE AND signed = ? AND special_edition = ?",
                (title, new_signed, new_special),
            ).fetchone()

            if row is None:
                connection.execute(
                    "INSERT INTO library (title, sku, author, quantity, signed, "
                    "special_edition, reading_status, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (title, sku, author, quantity, new_signed, new_special,
                     reading_status, notes),
                )
            else:
                connection.execute(
                    "UPDATE library SET quantity = quantity + ? WHERE id = ?",
                    (quantity, row["id"]),
                )
                if sku and not (row["sku"] or ""):
                    connection.execute("UPDATE library SET sku = ? WHERE id = ?",
                                       (sku, row["id"]))
                if author and not (row["author"] or ""):
                    connection.execute("UPDATE library SET author = ? WHERE id = ?",
                                       (author, row["id"]))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def edit_book(
    book_id: int,
    title: str,
    author: str | None = None,
    sku: str | None = None,
    quantity: int = 1,
    signed: bool = False,
    special_edition: bool = False,
    reading_status: str = "Unread",
    notes: str | None = None,
) -> None:
    """Update all editable fields on the row identified by *book_id*."""
    title = title.strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")
    if reading_status not in READING_STATUSES:
        reading_status = "Unread"
    sku    = _normalize_sku(sku)
    author = (author or "").strip() or None
    notes  = (notes or "").strip() or None

    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM library WHERE id = ?", (book_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Book ID {book_id} not found.")
        connection.execute(
            "UPDATE library SET title=?, author=?, sku=?, quantity=?, signed=?, "
            "special_edition=?, reading_status=?, notes=? WHERE id=?",
            (title, author, sku, quantity, int(bool(signed)),
             int(bool(special_edition)), reading_status, notes, book_id),
        )


def update_cover_url(book_id: int, cover_url: str) -> None:
    """Store a fetched cover URL against *book_id*."""
    _ensure_db()
    with get_connection() as connection:
        connection.execute(
            "UPDATE library SET cover_url = ? WHERE id = ?", (cover_url, book_id)
        )


def remove_book(book_id: int) -> None:
    """Decrement quantity by 1; delete the row when it reaches zero."""
    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, quantity FROM library WHERE id = ?", (book_id,)
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Book ID {book_id} was not found in the inventory. "
                "It may have already been removed."
            )
        if row["quantity"] > 1:
            connection.execute(
                "UPDATE library SET quantity = quantity - 1 WHERE id = ?", (book_id,)
            )
        else:
            connection.execute("DELETE FROM library WHERE id = ?", (book_id,))


def find_by_sku(sku: str) -> list[dict]:
    """Return all library rows whose sku matches *sku*."""
    sku = _normalize_sku(sku)
    if not sku:
        return []
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, sku, author, quantity, signed, special_edition, "
            "reading_status, notes, cover_url FROM library WHERE sku = ?", (sku,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


# ── Wishlist ──────────────────────────────────────────────────────────────────

def load_wishlist() -> list[dict]:
    """Return all wishlist entries sorted by title."""
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, author, notes FROM wishlist ORDER BY title COLLATE NOCASE"
        ).fetchall()
    return [
        {"id": r["id"], "title": r["title"],
         "author": r["author"] or "", "notes": r["notes"] or ""}
        for r in rows
    ]


def add_to_wishlist(title: str, author: str | None = None,
                    notes: str | None = None) -> None:
    """Add a book to the wishlist."""
    title = title.strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    author = (author or "").strip() or None
    notes  = (notes or "").strip() or None
    _ensure_db()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO wishlist (title, author, notes) VALUES (?, ?, ?)",
            (title, author, notes),
        )


def remove_from_wishlist(wishlist_id: int) -> None:
    """Remove an entry from the wishlist by id."""
    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM wishlist WHERE id = ?", (wishlist_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Wishlist entry {wishlist_id} not found.")
        connection.execute("DELETE FROM wishlist WHERE id = ?", (wishlist_id,))


def move_wishlist_to_library(
    wishlist_id: int,
    quantity: int = 1,
    signed: bool = False,
    special_edition: bool = False,
    reading_status: str = "Unread",
) -> None:
    """Move a wishlist entry into the library and remove it from the wishlist."""
    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT title, author, notes FROM wishlist WHERE id = ?", (wishlist_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Wishlist entry {wishlist_id} not found.")
        title  = row["title"]
        author = row["author"]
        notes  = row["notes"]

    add_book(title, quantity, signed=signed, special_edition=special_edition,
             author=author, reading_status=reading_status, notes=notes)
    remove_from_wishlist(wishlist_id)
