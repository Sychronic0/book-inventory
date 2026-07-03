"""Release script for Samantha's Book Library.

Usage:
    python release.py

This script will:
  1. Read the current version from VERSION
  2. Ask for a changelog summary
  3. Commit and push to GitHub
  4. Post a formatted embed to Discord announcing the update

Setup (one time only):
  - Create a Discord webhook in your server channel
  - Add the webhook URL to a file called .discord_webhook in this folder
    (just paste the URL on a single line, nothing else)
  - The .discord_webhook file is in .gitignore so it stays private
"""

import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

WEBHOOK_FILE = Path(__file__).parent / ".discord_webhook"
VERSION_FILE = Path(__file__).parent / "VERSION"
RELEASES_URL = "https://github.com/Sychronic0/book-inventory/releases"
REPO_URL     = "https://github.com/Sychronic0/book-inventory"


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"


def read_webhook() -> str | None:
    if not WEBHOOK_FILE.exists():
        print("⚠  No .discord_webhook file found.")
        print(f"   Create {WEBHOOK_FILE} and paste your Discord webhook URL in it.")
        return None
    url = WEBHOOK_FILE.read_text().strip()
    if not url.startswith("https://discord.com/api/webhooks/"):
        print("⚠  .discord_webhook doesn't look like a valid Discord webhook URL.")
        return None
    return url


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


def post_discord(webhook_url: str, version: str, changelog: str) -> bool:
    """Post a formatted embed to Discord. Returns True on success."""
    print("\n── Discord ──────────────────────────────────")

    embed = {
        "title": f"📚 Book Library — v{version} Released",
        "description": changelog,
        "color": 0x4a2d6b,  # bruise-purple from the Forest theme
        "fields": [
            {
                "name": "How to update",
                "value": "Run `python updater.py` in your book-inventory folder",
                "inline": False,
            },
            {
                "name": "Full changelog",
                "value": f"[View on GitHub]({RELEASES_URL})",
                "inline": True,
            },
        ],
        "footer": {
            "text": f"Samantha's Book Library • v{version}",
        },
    }

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
                print("  ✓ Posted to Discord")
                return True
            else:
                print(f"  ⚠  Unexpected response: {resp.status}")
                return False
    except urllib.error.HTTPError as e:
        print(f"  ✗ Discord error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"  ✗ Failed to post to Discord: {e}")
        return False


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
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    # Push to GitHub
    pushed = git_push(version, changelog)
    if not pushed:
        print("\n✗ Git push failed — Discord notification skipped.")
        return

    # Post to Discord
    webhook_url = read_webhook()
    if webhook_url:
        post_discord(webhook_url, version, changelog)
    else:
        print("  Skipping Discord — no webhook configured.")

    print("\n✓ Release complete!")
    print(f"  View at: {REPO_URL}")


if __name__ == "__main__":
    main()
