"""Fetch images from Unsplash + PMC figures for multi-scene reels."""
import os
from pathlib import Path
import requests


def fetch_scene_images(
    scenes: list[dict],
    figure_urls: list[str],
    output_dir: Path,
) -> list[Path]:
    """Fetch one image per scene. Use PMC figures when available, else Unsplash."""
    api_key = os.environ.get("UNSPLASH_API_KEY")
    paths = []
    fig_idx = 0

    for i, scene in enumerate(scenes):
        out = output_dir / f"scene_{i}.jpg"

        # Use PMC figure for "finding" or "context" scenes if available
        if scene.get("type") in ("finding", "context") and fig_idx < len(figure_urls):
            if _download_image(figure_urls[fig_idx], out):
                fig_idx += 1
                paths.append(out)
                continue
            fig_idx += 1

        # Fallback to Unsplash
        query = scene.get("image_query", "science")
        if api_key and _fetch_unsplash(api_key, query, out):
            paths.append(out)
        else:
            _create_placeholder(out, query)
            paths.append(out)

    return paths


def fetch_for_topic(topic: str, output_path: Path) -> None:
    """Single image fetch (backward compat)."""
    api_key = os.environ.get("UNSPLASH_API_KEY")
    if api_key:
        _fetch_unsplash(api_key, topic, output_path)
    else:
        _create_placeholder(output_path, topic)


def _fetch_unsplash(api_key: str, query: str, output_path: Path) -> bool:
    try:
        resp = requests.get("https://api.unsplash.com/photos/random", params={
            "query": query, "orientation": "portrait",
            "w": 1080, "h": 1920, "client_id": api_key,
        }, timeout=10)
        resp.raise_for_status()
        image_url = resp.json()["urls"]["regular"]
        img_resp = requests.get(image_url, timeout=15)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)
        print(f"Unsplash: {output_path.name} ({query})")
        return True
    except Exception as e:
        print(f"Unsplash error ({query}): {e}")
        return False


def _download_image(url: str, output_path: Path) -> bool:
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "RevueReelsBot/1.0"
        })
        resp.raise_for_status()
        if len(resp.content) < 5000:
            return False
        output_path.write_bytes(resp.content)
        print(f"PMC figure: {output_path.name}")
        return True
    except Exception:
        return False


def _create_placeholder(path: Path, text: str = "Science") -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1080, 1920), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        draw.text((540, 960), text[:20], fill=(100, 100, 140), anchor="mm")
        img.save(path)
    except Exception:
        pass
