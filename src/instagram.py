"""Post Reel to Instagram using instagrapi."""
import os
from pathlib import Path
from instagrapi import Client


def post_reel(reel_path: Path, caption: str) -> None:
    """
    Login to Instagram and post the reel video.
    """
    username = os.environ.get("INSTAGRAM_USERNAME")
    password = os.environ.get("INSTAGRAM_PASSWORD")

    if not username or not password:
        raise ValueError("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD required")

    try:
        client = Client()
        client.login(username, password)
        print(f"Logged in as {username}")

        # Post reel
        media = client.clip_upload(
            video_path=str(reel_path),
            caption=caption,
            thumbnail=None,
        )
        print(f"Reel posted: {media.pk}")
        client.logout()
    except Exception as e:
        print(f"Instagram error: {e}")
        raise
