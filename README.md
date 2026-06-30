# Samantha's Book Library

A Victorian-styled desktop app for tracking which books you own and how many copies you have.

## Run (This is just for me, when you download, there's a batch script.)

```powershell
cd C:\Users\black\book-inventory
python main.py
```

## Features

- View all books with individual counts
- See total titles and total copies at a glance
- Add books (duplicate titles increase the count)
- Remove selected books from your collection
- **Autocomplete** — start typing a title and pick from suggestions (Open Library)
- **SQLite database** — your library is stored in `library.db`

Your collection is saved in `library.db`. If you had data in `books.json`, it is imported automatically on first run. Book suggestions are cached locally in the same database for offline use after you've searched once.

## How the database works

| File | Purpose |
|------|---------|
| `library.db` | SQLite database with your owned books and a cached suggestion catalog |
| `database.py` | Creates tables and handles migration from `books.json` |
| `book_search.py` | Queries Open Library as you type; falls back to cached titles offline |
| `book_store.py` | Add, remove, and load books from the database |

Internet is needed the first time you search for a new title. After that, matching titles can appear from the local cache even without a connection.

## Keeping Your Library Across Computers

Your book data is stored in `library.db` in the app folder.

To access it on any computer:
1. Move the entire `book-inventory` folder into your OneDrive folder
   (e.g. `C:\Users\black\OneDrive\book-inventory`)
2. Run the app from there as normal
3. OneDrive will automatically sync your library to any computer
   you're signed into

**Never move just the `.db` file on its own — keep the whole folder together.**

## Running the App
Double-click `run.bat` to launch.

Or from the terminal:
    cd path\to\book-inventory
    python main.py