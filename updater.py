"""Samantha's Book Library — Auto-updater.

Run this script from the book-inventory folder to pull the latest
version of all application files from GitHub.

Usage:
    python updater.py

Your library data (library.db) is never touched.
"""

import urllib.request
import os
import sys
from pathlib import Path

REPO_BASE = "https://raw.githubusercontent.com/Sychronic0/book-inventory/main/"

FILES = [
    "main.py",
    "book_store.py",
    "database.py",
    "theme.py",
    "fonts.py",
    "autocomplete.py",
    "book_search.py",
    "barcode_scanner.py",
    "updater.py",
]

def main() -> None:
    app_dir = Path(__file__).parent
    print("Samantha's Book Library — Updater")
    print("=" * 40)
    print(f"Updating files in: {app_dir}\n")

    failed = []
    for filename in FILES:
        url  = REPO_BASE + filename
        dest = app_dir / filename
        try:
            print(f"  Downloading {filename}...", end=" ", flush=True)
            urllib.request.urlretrieve(url, dest)
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")
            failed.append(filename)

    print()
    if failed:
        print(f"⚠ {len(failed)} file(s) failed to update: {', '.join(failed)}")
        print("  Your existing files were not changed for those.")
    else:
        print("✓ All files updated successfully!")

    print("\nRestart the app to use the new version.")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()