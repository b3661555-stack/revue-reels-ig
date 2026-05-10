"""Fetch images from Unsplash + PMC figures for multi-scene reels."""
import os
from pathlib import Path
import requests

try:
    import fitz
except ImportError:
    fitz = None


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

        if scene.get("type") == "paper":
            paths.append(out)
            continue

        if scene.get("type") in ("finding", "method", "context") and fig_idx < len(figure_urls):
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


def extract_figures_from_pdf(pdf_path: Path, output_dir: Path, max_figures: int = 5) -> list[Path]:
    """Extract figure images from PDF using PyMuPDF."""
    if fitz is None:
        return []
    try:
        doc = fitz.open(str(pdf_path))
        figures = []
        for page_num in range(min(len(doc), 15)):
            page = doc[page_num]
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue
                image_bytes = base_image["image"]
                w, h = base_image["width"], base_image["height"]
                if w < 300 or h < 200 or len(image_bytes) < 10000:
                    continue
                ext = base_image.get("ext", "png")
                out = output_dir / f"pdf_fig_p{page_num}_{img_idx}.{ext}"
                out.write_bytes(image_bytes)
                figures.append(out)
                if len(figures) >= max_figures:
                    break
            if len(figures) >= max_figures:
                break
        doc.close()
        if figures:
            print(f"  PDF figures extracted: {len(figures)}")
        return figures
    except Exception as e:
        print(f"  PDF figure extraction failed: {e}")
        return []


def render_pdf_page1(pdf_path: Path, output_path: Path) -> bool:
    """Render first page of PDF as high-res PNG."""
    if fitz is None:
        print("  pymupdf not available, skipping PDF render")
        return False
    try:
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=200)
        pix.save(str(output_path))
        doc.close()
        print(f"  PDF page 1 rendered: {pix.width}x{pix.height}")
        return True
    except Exception as e:
        print(f"  PDF render failed: {e}")
        return False
