# Book Library

A themed desktop app for tracking your personal book collection — owned books,
wishlist, reading status, and more.

![Version](https://img.shields.io/badge/version-1.1.2-purple)

---

## Running the App

### Option A — EXE (recommended for most users)
Download `BookLibrary.exe` from the [latest release](https://github.com/Sychronic0/book-inventory/releases)
and double-click it. No Python or dependencies needed.

Your library data (`library.db`) is saved next to the EXE — keep them together.

### Option B — Python (developers)
```powershell
cd path\to\book-inventory
python main.py
```
Requires Python 3.11+.

---

## First Launch
On first launch you'll be asked for your name. The app titles itself
accordingly — e.g. **Samantha's Book Library**. You can change this later
via **Settings → Change Library Name…**

---

## Features

### Library Tab
| Feature | Description |
|---------|-------------|
| Add books | Title, author, SKU, quantity, signed/special edition flags, reading status, notes |
| Edit books | Double-click any row to edit all fields |
| Remove books | Decrements quantity; deletes row when it reaches zero |
| Scan barcode | Webcam or manual ISBN lookup auto-fills the add form |
| Wishlist | Toggle to a separate wishlist; move entries into your library when acquired |
| Browse All | Fullscreen view of your entire collection with its own search |
| Export CSV | **File → Export Library to CSV…** saves a spreadsheet of your library |
| Sortable columns | Click any column header to sort; click again to reverse |

### Search Tab
| Feature | Description |
|---------|-------------|
| Live search | Filters across title, author, SKU, reading status, and edition type |
| Type filter | Narrow to Regular / Signed / Special Edition / Signed Special Edition |
| Table view | Standard sortable table |
| Grid view | Shelf of book covers with title, author, status badge, and type badge |

### Stats Tab
- Summary strip: titles, copies, signed, special editions, unique authors
- Reading status breakdown (Unread / Reading / Finished / DNF)
- Edition type breakdown
- Top authors by copy count
- Titles with multiple copies

### Themes
**View → Theme** switches between:
- **Victorian** — warm parchment, mahogany, burgundy, gold
- **Forest** — body-rot horror palette (near-black violet, bruise-purple, moss green)

Your theme choice is remembered between launches.

### Reading Status
Every book tracks: **Unread · Reading · Finished · DNF**

---

## Barcode Scanning
The **📷 Scan Barcode** button supports webcam scanning and manual ISBN entry.
Results auto-fill the add form for review before saving.

Webcam scanning requires extra packages (not needed for the EXE build):
```powershell
pip install opencv-python pyzbar
```

---

## Keeping Your Data Across Computers
Your library is stored in `library.db` next to the app. To sync across
computers, move the entire folder into **OneDrive** — it syncs automatically.

---

## Updates

When a new version is available, a banner appears in the Library tab.

**EXE users:** download the new `BookLibrary.exe` from the releases page.

**Python users:** run the updater:
```powershell
python updater.py
```
Your library data is never touched during updates.

---

## Building the EXE (developers)

1. Install PyInstaller: `pip install pyinstaller`
2. Place `app_icon.ico` in the repo folder
3. Run: `build.bat` (or `pyinstaller book_library.spec --clean`)
4. Output: `dist\BookLibrary.exe`

---

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | Application UI (Tkinter) |
| `book_store.py` | Library and wishlist CRUD |
| `database.py` | Schema, migrations, prefs |
| `book_search.py` | Open Library search + ISBN lookup |
| `barcode_scanner.py` | Webcam barcode decoding |
| `autocomplete.py` | Title autocomplete widget |
| `theme.py` | Victorian and Forest palettes |
| `fonts.py` | Font resolution |
| `updater.py` | Pulls latest files from GitHub |
| `release.py` | Commits, pushes, triggers Discord notification |
| `build.bat` | Builds the Windows EXE |
| `book_library.spec` | PyInstaller build spec |
| `VERSION` | Current version number |
| `library.db` | Your book data (SQLite) — never committed |

---

## Discord Notifications
Releases are announced automatically in Discord via GitHub Actions.
The workflow triggers whenever `VERSION` changes on a push to `main`.

To set up: add your Discord webhook URL as a repository secret named
`DISCORD_WEBHOOK` in **GitHub → Settings → Secrets and variables → Actions**.
