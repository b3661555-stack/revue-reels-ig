"""Fetch scientific images from Unsplash API."""
import os
from pathlib import Path
import requests


def fetch_for_topic(topic: str, output_path: Path) -> None:
    """Download image from Unsplash for the given topic."""
    api_key = os.environ.get("UNSPLASH_API_KEY")
    if not api_key:
        raise ValueError("UNSPLASH_API_KEY not set")

    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": topic,
        "orientation": "portrait",
        "w": 1080,
        "h": 1920,
        "client_id": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        image_url = data["urls"]["regular"]
        img_resp = requests.get(image_url, timeout=10)
        img_resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(img_resp.content)
        print(f"Image saved: {output_path}")
    except Exception as e:
        print(f"Unsplash error: {e}")
        # Create placeholder
        _create_placeholder(output_path)


def _create_placeholder(path: Path) -> None:
    """Create a simple placeholder image if fetch fails."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1080, 1920), color=(50, 50, 50))
        draw = ImageDraw.Draw(img)
        draw.text((540, 960), "Science", fill=(255, 255, 255), anchor="mm")
        img.save(path)
    except Exception as e:
        print(f"Placeholder creation failed: {e}")
