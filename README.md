# Samantha's Book Library

A Victorian/Forest-themed desktop app for tracking which books you own, how
many copies you have, and what you still want to read.

## Running the App

Double-click `run.bat`, or from a terminal:

```powershell
cd path\to\book-inventory
python main.py
```

## Keeping Your Library Across Computers

Your book data lives in `library.db` in the app folder. To access it on any
computer, move the entire `book-inventory` folder into your OneDrive folder
(e.g. `C:\Users\YourName\OneDrive\book-inventory`) and run it from there.
OneDrive syncs the database automatically. **Never move just the `.db` file
on its own — keep the whole folder together.**

## Updating to a New Version

When a new version is pushed, the app shows an update banner at the bottom
of the Library tab. Click it to open the releases page, then run:

```powershell
python updater.py
```

This pulls the latest `.py` files from GitHub. **Your library data is never
touched** — only the application code is replaced.

## Features

### Library tab
- View all owned books with quantity, author, SKU, signed/special edition
  flags, reading status, and notes
- **Edit any book** — double-click a row to open the edit dialog
- **Add books** — duplicate (title + edition combo) entries increase quantity
  rather than creating a new row
- **Remove books** — decreases quantity by one; deletes the row at zero
- **Scan Barcode** — webcam or manual ISBN lookup auto-fills the add form
  (see Barcode Scanning below)
- **Wishlist toggle** — switch the tab to a separate wishlist of books you
  want but don't own yet; entries can be moved straight into your library
- **Browse All** — fullscreen view of your entire collection with its own
  search bar
- **Export to CSV** — File menu or the Export CSV button saves your whole
  library as a spreadsheet

### Search tab
- Live search across title, author, SKU, reading status, and edition type
- Filter by type: Regular / Signed / Special Edition / Signed Special Edition
- **Table or Grid view** — toggle between a sortable table and a shelf of
  book covers, each showing title, author, quantity, and a type badge.
  Cover art is fetched from Open Library when available.

### Themes
View > Theme switches between **Victorian** (warm parchment, mahogany, gold)
and **Forest** (body-rot horror — near-black violet, bruise-purple, sickly
moss). Your choice is remembered between launches.

### Reading Status
Every book can be marked Unread, Reading, Finished, or DNF (Did Not Finish).

## Barcode Scanning

The Scan Barcode button supports two modes:

1. **Webcam scan** — point your camera at the ISBN barcode on a book's back
   cover; it auto-detects and looks up the title.
2. **Manual entry** — type the ISBN number directly if you don't have a
   webcam or the scan doesn't catch.

Either way, results fill the Add form for you to review before saving —
nothing is added automatically.

Webcam scanning requires two extra packages:

```powershell
pip install opencv-python pyzbar
```

If these aren't installed, manual ISBN entry still works; the camera button
is simply disabled with a note telling you what to install.

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | The application UI (Tkinter) |
| `book_store.py` | Add, edit, remove, and load books and wishlist entries |
| `database.py` | Creates tables, handles schema migrations |
| `book_search.py` | Open Library search + ISBN lookup, with local cache fallback |
| `barcode_scanner.py` | Webcam capture and barcode decoding |
| `autocomplete.py` | Title autocomplete widget used in the Add form |
| `theme.py` | Victorian and Forest color/font palettes, live theme switching |
| `fonts.py` | Resolves available display/body fonts on the current machine |
| `updater.py` | Pulls the latest app files from GitHub |
| `VERSION` | Current version number, checked against GitHub on launch |
| `library.db` | Your book and wishlist data (SQLite) |

Internet is needed the first time you search for a new title, fetch cover
art, or look up an ISBN. Matching titles can still appear from the local
cache offline after you've searched once.
