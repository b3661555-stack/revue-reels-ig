"""Assemble vertical reel video with Ken Burns effect and text overlay."""
from pathlib import Path
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips


TARGET_W, TARGET_H = 1080, 1920
ZOOM_FACTOR = 0.15


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _prepare_base_image(image_path: Path) -> Image.Image:
    """Scale and crop image to 1080x1920 with extra margin for Ken Burns."""
    img = Image.open(image_path).convert("RGB")
    margin = 1 + ZOOM_FACTOR
    w, h = int(TARGET_W * margin), int(TARGET_H * margin)
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _ken_burns_frame(base_img: np.ndarray, t: float, duration: float) -> np.ndarray:
    """Slow zoom-in effect over time."""
    progress = t / duration
    current_zoom = 1.0 + ZOOM_FACTOR * progress
    h, w = base_img.shape[:2]
    new_w = int(TARGET_W * current_zoom)
    new_h = int(TARGET_H * current_zoom)
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    cropped = base_img[top:top + new_h, left:left + new_w]
    pil = Image.fromarray(cropped).resize((TARGET_W, TARGET_H), Image.LANCZOS)
    return np.array(pil)


def _add_text_overlay(frame: np.ndarray, text: str) -> np.ndarray:
    """Add gradient overlay + text at bottom of frame."""
    img = Image.fromarray(frame).convert("RGBA")
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Gradient from transparent to dark at bottom
    for y in range(TARGET_H - 600, TARGET_H):
        alpha = int(180 * (y - (TARGET_H - 600)) / 600)
        draw_ov.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    font = _get_font(52)
    wrapped = textwrap.fill(text, width=28)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (TARGET_W - tw) // 2
    y = TARGET_H - th - 200

    # Text shadow
    draw.text((x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), wrapped, font=font, fill="white")

    return np.array(img.convert("RGB"))


def assemble_reel(
    image_path: Path,
    audio_path: Path,
    text: str,
    output_path: Path,
    duration: float = 45.0,
) -> None:
    """Create vertical Instagram Reel with Ken Burns effect."""
    try:
        audio = AudioFileClip(str(audio_path))
        duration = max(min(audio.duration + 1.0, 59.0), 15.0)

        base_img = np.array(_prepare_base_image(image_path))

        bg_clip = ImageClip(base_img).set_duration(duration)
        bg_clip = bg_clip.fl(lambda gf, t: _ken_burns_frame(base_img, t, duration))
        bg_clip = bg_clip.set_duration(duration)

        # Apply text overlay to each frame
        video = bg_clip.fl_image(lambda frame: _add_text_overlay(frame, text))
        video = video.set_audio(audio)

        video.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            verbose=False,
            logger=None,
        )
        print(f"Reel assembled: {output_path} ({duration:.1f}s)")
    except Exception as e:
        print(f"MoviePy error: {e}")
        raise
