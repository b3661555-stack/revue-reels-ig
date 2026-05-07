"""Post Reel to Instagram using instagrapi with session persistence."""
import base64
import json
import os
from pathlib import Path
from instagrapi import Client


def _load_session(client: Client) -> bool:
    """Load session from IG_SESSION_B64 env var if available."""
    session_b64 = os.environ.get("IG_SESSION_B64")
    if not session_b64:
        return False
    try:
        settings = json.loads(base64.b64decode(session_b64))
        client.set_settings(settings)
        client.get_timeline_feed()
        print("Session restored from IG_SESSION_B64")
        return True
    except Exception as e:
        print(f"Session restore failed, will login fresh: {e}")
        return False


def post_reel(reel_path: Path, caption: str) -> None:
    username = os.environ.get("INSTAGRAM_USERNAME")
    password = os.environ.get("INSTAGRAM_PASSWORD")

    if not username or not password:
        raise ValueError("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD required")

    client = Client()

    if not _load_session(client):
        client.login(username, password)
        print(f"Logged in as {username}")

    media = client.clip_upload(
        video_path=str(reel_path),
        caption=caption,
        thumbnail=None,
    )
    print(f"Reel posted: {media.pk}")
