"""
Run this script to refresh Google OAuth credentials whenever token.pickle expires.

Usage:
    python refresh_credentials.py
    python refresh_credentials.py --rebuild   # also rebuilds & restarts the Docker agent
"""

import argparse
import os
import pickle
import subprocess
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = Path("token.pickle")


def _credentials_file() -> Path:
    env_path = os.getenv("GOOGLE_CREDENTIALS_FILE")
    if env_path:
        return Path(env_path)

    for candidate in ("credentials.json", "Credentials.json"):
        path = Path(candidate)
        if path.exists():
            return path

    return Path("credentials.json")


def refresh():
    creds_file = _credentials_file()
    if not creds_file.exists():
        print(
            f"ERROR: {creds_file} not found. Place your OAuth client secrets file in project root "
            "or set GOOGLE_CREDENTIALS_FILE."
        )
        sys.exit(1)

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print(f"Removed stale {TOKEN_FILE}")

    print("Opening browser for Google OAuth consent...")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    creds = flow.run_local_server(port=0)

    with TOKEN_FILE.open("wb") as f:
        pickle.dump(creds, f)

    print(f"Saved new credentials to {TOKEN_FILE}")


def rebuild_docker():
    print("\nRebuilding and restarting Docker agent...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--build", "agent"],
        check=False,
    )
    if result.returncode != 0:
        print("WARNING: Docker rebuild exited with a non-zero status.")
    else:
        print("Agent restarted successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh Google OAuth token.pickle")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild and restart the Docker agent after refreshing credentials",
    )
    args = parser.parse_args()

    refresh()

    if args.rebuild:
        rebuild_docker()
