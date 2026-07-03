"""Release script for Samantha's Book Library.

Usage:
    python release.py

This script will:
  1. Read the current version from VERSION
  2. Ask for a changelog summary
  3. Commit and push to GitHub
  4. GitHub Actions automatically posts a Discord notification

No local setup needed — Discord notifications are handled server-side
via GitHub Actions using a secret webhook stored in the repo settings.
"""

import subprocess
from pathlib import Path

VERSION_FILE = Path(__file__).parent / "VERSION"
REPO_URL     = "https://github.com/Sychronic0/book-inventory"


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"


def git_push(version: str, message: str) -> bool:
    """Stage all changes, commit, and push. Returns True on success."""
    print("\n── Git ─────────────────────────────────────")
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"v{version} — {message}"],
        ["git", "push", "origin", "main"],
    ]
    for cmd in commands:
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(f"  {result.stdout.strip()}")
        if result.returncode != 0:
            print(f"  ✗ Failed: {result.stderr.strip()}")
            return False
    print("  ✓ Pushed to GitHub")
    return True


def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║   Book Library — Release Script          ║")
    print("╚══════════════════════════════════════════╝\n")

    version = read_version()
    print(f"Current version: {version}")

    changelog = input("\nWhat changed in this version?\n> ").strip()
    if not changelog:
        print("Aborted — changelog cannot be empty.")
        return

    print(f"\nReady to release v{version}:")
    print(f"  Changelog : {changelog}")
    print(f"\nNote: Discord will be notified automatically via GitHub Actions.")
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    pushed = git_push(version, changelog)
    if not pushed:
        print("\n✗ Git push failed.")
        return

    print("\n✓ Release complete!")
    print(f"  GitHub Actions will post to Discord shortly.")
    print(f"  View at: {REPO_URL}")


if __name__ == "__main__":
    main()