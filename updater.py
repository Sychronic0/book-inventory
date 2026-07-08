"""Samantha's Book Library — Auto-updater.

Run this script from the book-inventory folder to pull the latest
version of all application files from GitHub.

Usage:
    python updater.py                        # manual run
    python updater.py --restart python main.py  # called by the app

Your library data (library.db) is never touched.
"""

import sys
import subprocess
import urllib.request
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
    # Parse --restart flag
    restart_cmd = None
    args = sys.argv[1:]
    if args and args[0] == "--restart":
        restart_cmd = args[1:]  # e.g. ["python", "main.py"]

    app_dir = Path(__file__).parent
    print("Samantha's Book Library — Updater")
    print("=" * 40)
    if not restart_cmd:
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
        print(f"⚠  {len(failed)} file(s) failed to update: {', '.join(failed)}")
    else:
        print("✓ All files updated successfully!")

    if restart_cmd:
        print(f"\nRestarting app...")
        subprocess.Popen(restart_cmd, cwd=str(app_dir))
    else:
        print("\nRestart the app to use the new version.")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
