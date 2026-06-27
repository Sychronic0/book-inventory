"""Book storage layer — CRUD against the local SQLite inventory database.

Responsibilities:
  - add_book / remove_book / load_books / unique_titles / total_count
    for the library table
  - normalize SKU input (empty/whitespace -> None)
  - delegate schema init and one-shot books.json migration to database.py

Inventory model:
  - Each row in `library` represents a distinct edition of a title:
      (title, signed, special_edition) is the natural key.
  - Adding the same title with the same edition flags increases that
    row's quantity. Adding it with different flags creates a new row,
    so a Regular, a Signed, and a Special Edition of the same book each
    get their own row and are listed separately in the UI.
  - remove_book() decrements quantity by 1 and only deletes the row
    when quantity reaches zero.
  - Results are sorted by title (A→Z) then edition type so all copies
    of a title always appear together.

SKU rules:
  - A SKU belongs to one (title + edition) combination.
  - Cross-combination SKU conflicts raise ValueError before any row is
    touched.
  - An existing SKU is never silently overwritten; mismatches raise.
"""

from pathlib import Path

from database import get_connection, init_db, migrate_from_json

DATA_FILE = Path(__file__).parent / "books.json"

# Edition-type sort order: Regular → Signed → Special → Signed+Special
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


def load_books() -> list[dict]:
    """Return all books grouped by title (A→Z) then edition type.

    Within each title the order is:
        Regular → Signed → Special Edition → Signed Special Edition

    Each entry is a dict with keys:
        id, title, sku, author, quantity, signed, special_edition
    """
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, sku, author, quantity, signed, special_edition
            FROM library
            """
        ).fetchall()

    books = [
        {
            "id": row["id"],
            "title": row["title"],
            "sku": row["sku"] or "",
            "author": row["author"] or "",
            "quantity": row["quantity"],
            "signed": bool(row["signed"]),
            "special_edition": bool(row["special_edition"]),
        }
        for row in rows
    ]

    books.sort(key=lambda b: (
        b["title"].casefold(),
        _EDITION_ORDER[(b["signed"], b["special_edition"])],
    ))
    return books


def find_by_sku(sku: str) -> list[dict]:
    """Return all library rows whose sku matches *sku* (case-sensitive exact match).

    SKU is the unique identifier for a (title + edition) combination, so
    in practice this returns 0 or 1 rows — but the schema permits sharing
    a SKU across distinct editions, so we return a list for safety.

    The sku parameter is normalized the same way add_book() normalizes
    input, so callers can pass either a raw or stripped value.
    """
    sku = _normalize_sku(sku)
    if not sku:
        return []
    _ensure_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, sku, author, quantity, signed, special_edition
            FROM library
            WHERE sku = ?
            """,
            (sku,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "sku": row["sku"] or "",
            "author": row["author"] or "",
            "quantity": row["quantity"],
            "signed": bool(row["signed"]),
            "special_edition": bool(row["special_edition"]),
        }
        for row in rows
    ]


def unique_titles(books: list[dict]) -> int:
    """Return the number of distinct titles in *books* with quantity > 0.

    Accepts the list returned by load_books() so the caller avoids a
    second database round-trip.
    """
    return len({book["title"].casefold() for book in books if book["quantity"] > 0})


def add_book(
    title: str,
    quantity: int = 1,
    sku: str | None = None,
    signed: bool = False,
    special_edition: bool = False,
    author: str | None = None,
) -> None:
    """Add *quantity* copies of *title* to the inventory.

    Each unique combination of (title, signed, special_edition) is stored
    as its own row, so Regular, Signed, and Special Edition copies of the
    same title are tracked separately.

    - If a row for this exact (title, signed, special_edition) already
      exists, its quantity is increased.
    - A missing SKU or author on an existing row is filled in; existing
      values are never overwritten.
    - Raises ValueError if:
        - *title* is empty
        - *quantity* is less than 1
        - *sku* is already assigned to a different (title + edition)
        - *sku* conflicts with the existing SKU for the same (title + edition)

    All writes happen inside a single SQLite transaction; any ValueError
    raised mid-flight rolls the transaction back so the database never
    ends up in a half-applied state.
    """
    title = title.strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")
    sku = _normalize_sku(sku)
    author = (author or "").strip() or None

    new_signed = int(bool(signed))
    new_special = int(bool(special_edition))

    _ensure_db()
    with get_connection() as connection:
        try:
            # ── Validate first: do all reads + SKU conflict checks before
            # touching any rows, so we can raise cleanly without side effects.
            if sku:
                sku_row = connection.execute(
                    "SELECT id, title, signed, special_edition FROM library WHERE sku = ?",
                    (sku,),
                ).fetchone()
                if sku_row is not None:
                    same_edition = (
                        sku_row["title"].casefold() == title.casefold()
                        and int(sku_row["signed"]) == new_signed
                        and int(sku_row["special_edition"]) == new_special
                    )
                    if not same_edition:
                        raise ValueError(
                            f'SKU "{sku}" is already assigned to a different '
                            f'(title, signed, special_edition) combination.'
                        )

            row = connection.execute(
                """
                SELECT id, quantity, sku, author
                FROM library
                WHERE title = ? COLLATE NOCASE
                  AND signed = ?
                  AND special_edition = ?
                """,
                (title, new_signed, new_special),
            ).fetchone()

            if row is None:
                connection.execute(
                    """
                    INSERT INTO library (title, sku, author, quantity, signed, special_edition)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (title, sku, author, quantity, new_signed, new_special),
                )
            else:
                connection.execute(
                    "UPDATE library SET quantity = quantity + ? WHERE id = ?",
                    (quantity, row["id"]),
                )
                # Fill missing SKU/author; never overwrite existing values.
                if sku and not (row["sku"] or ""):
                    connection.execute(
                        "UPDATE library SET sku = ? WHERE id = ?",
                        (sku, row["id"]),
                    )
                if author and not (row["author"] or ""):
                    connection.execute(
                        "UPDATE library SET author = ? WHERE id = ?",
                        (author, row["id"]),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def remove_book(book_id: int) -> None:
    """Remove one copy of the book identified by *book_id* from inventory.

    Decrements the quantity by 1. When quantity reaches zero the row is
    deleted from the database entirely.

    Raises ValueError if *book_id* does not exist in the library.
    """
    _ensure_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, quantity FROM library WHERE id = ?",
            (book_id,),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Book ID {book_id} was not found in the inventory. "
                "It may have already been removed."
            )

        if row["quantity"] > 1:
            # Decrease the stock count by one copy.
            connection.execute(
                "UPDATE library SET quantity = quantity - 1 WHERE id = ?",
                (book_id,),
            )
        else:
            # Last copy removed — delete the inventory record entirely.
            connection.execute("DELETE FROM library WHERE id = ?", (book_id,))


def total_count(books: list[dict]) -> int:
    """Return the total number of copies across all books in *books*."""
    return sum(book["quantity"] for book in books)