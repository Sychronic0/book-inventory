"""Book search — online via Open Library, with local catalog fallback.

Pipeline:
  1. search_books(query) tries Open Library first.
  2. If the network call succeeds, results are cached into the catalog
     table (INSERT OR IGNORE) for future offline use.
  3. If the network call fails or returns nothing, search_local_catalog
     falls back to LIKE-matching against the cached titles/authors.

search_open_library returns at most DEFAULT_SEARCH_LIMIT results and
deduplicates by casefolded title. Each result carries:
  title, author, source_id (Open Library work key), sku (last path
  segment of source_id), display ("Title — Author").
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from database import get_connection, init_db

DEFAULT_SEARCH_LIMIT = 20


def lookup_by_isbn(isbn: str) -> dict | None:
    """Look up a single book by ISBN via Open Library.

    Returns a dict with title, author, source_id, sku, cover_url — or
    None if the ISBN has no match or the request fails.

    Accepts ISBN-10 or ISBN-13, with or without hyphens/spaces.
    """
    isbn = "".join(ch for ch in isbn.strip() if ch.isalnum())
    if not isbn:
        return None

    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    entry = payload.get(f"ISBN:{isbn}")
    if not entry:
        return None

    title = str(entry.get("title", "")).strip()
    if not title:
        return None

    authors = entry.get("authors") or []
    author = ", ".join(a.get("name", "") for a in authors[:2] if a.get("name"))

    source_id = str(entry.get("key", "")).strip()
    sku = sku_from_source_id(source_id) or isbn

    cover_url = ""
    cover = entry.get("cover") or {}
    if cover.get("medium"):
        cover_url = cover["medium"]

    return {
        "title": title,
        "author": author,
        "source_id": source_id,
        "sku": sku,
        "isbn": isbn,
        "cover_url": cover_url,
        "display": f"{title} — {author}" if author else title,
    }


def sku_from_source_id(source_id: str) -> str:
    source_id = source_id.strip()
    if not source_id:
        return ""
    return source_id.rstrip("/").split("/")[-1]


def search_open_library(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []

    params = urllib.parse.urlencode(
        {
            "q": query,
            "limit": limit,
            "fields": "title,author_name,key",
        }
    )
    url = f"https://openlibrary.org/search.json?{params}"

    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    results: list[dict] = []
    seen_titles: set[str] = set()

    for doc in payload.get("docs", []):
        title = str(doc.get("title", "")).strip()
        if not title:
            continue

        key = title.casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        authors = doc.get("author_name") or []
        author = ", ".join(authors[:2]) if authors else ""
        source_id = str(doc.get("key", "")).strip()
        sku = sku_from_source_id(source_id)

        results.append(
            {
                "title": title,
                "author": author,
                "source_id": source_id,
                "sku": sku,
                "display": f"{title} — {author}" if author else title,
            }
        )

    return results


def search_local_catalog(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    query = query.strip()
    if len(query) < 1:
        return []

    init_db()
    pattern = f"%{query}%"

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT title, author, source_id
            FROM catalog
            WHERE title LIKE ? COLLATE NOCASE
               OR author LIKE ? COLLATE NOCASE
               OR source_id LIKE ? COLLATE NOCASE
            ORDER BY title COLLATE NOCASE
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    return [
        {
            "title": row["title"],
            "author": row["author"] or "",
            "source_id": row["source_id"] or "",
            "sku": sku_from_source_id(row["source_id"] or ""),
            "display": f"{row['title']} — {row['author']}" if row["author"] else row["title"],
        }
        for row in rows
    ]


def cache_catalog_entries(entries: list[dict]) -> None:
    if not entries:
        return

    init_db()
    with get_connection() as connection:
        for entry in entries:
            connection.execute(
                """
                INSERT OR IGNORE INTO catalog (title, author, source_id)
                VALUES (?, ?, ?)
                """,
                (entry["title"], entry.get("author") or None, entry.get("source_id") or None),
            )


def search_books(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    online = search_open_library(query, limit=limit)
    if online:
        cache_catalog_entries(online)
        return online

    return search_local_catalog(query, limit=limit)
