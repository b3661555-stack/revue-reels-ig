"""Login to Instagram locally and save session as base64 for GitHub Secret."""
import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client

load_dotenv(Path(__file__).parent / ".env")

username = os.environ.get("INSTAGRAM_USERNAME")
password = os.environ.get("INSTAGRAM_PASSWORD")

if not username or not password:
    print("Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")
    sys.exit(1)

print(f"Logging in as {username}...")
client = Client()
client.login(username, password)
print("Login OK")

settings = client.get_settings()
session_b64 = base64.b64encode(json.dumps(settings).encode()).decode()

print(f"\nSession saved ({len(session_b64)} chars)")
print("\nPush to GitHub:")
print(f'  gh secret set IG_SESSION_B64 --body "{session_b64}" -R b3661555-stack/revue-reels-ig')
