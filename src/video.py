"""Multi-scene vertical reel with Ken Burns, article info, transitions."""
from pathlib import Path
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, ImageSequenceClip,
)

TARGET_W, TARGET_H = 1080, 1920
FPS = 24
ZOOM = 0.12


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths_bold = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    paths_regular = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in (paths_bold if bold else paths_regular):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _prepare_image(image_path: Path) -> np.ndarray:
    """Scale/crop to fill target + zoom margin."""
    img = Image.open(image_path).convert("RGB")
    m = 1 + ZOOM
    w, h = int(TARGET_W * m), int(TARGET_H * m)
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return np.array(img.crop((left, top, left + w, top + h)))


def _ken_burns_frame(base: np.ndarray, t: float, duration: float) -> np.ndarray:
    progress = t / max(duration, 0.1)
    zoom = 1.0 + ZOOM * progress
    new_w, new_h = int(TARGET_W * zoom), int(TARGET_H * zoom)
    h, w = base.shape[:2]
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    cropped = base[top:top + new_h, left:left + new_w]
    return np.array(Image.fromarray(cropped).resize((TARGET_W, TARGET_H), Image.LANCZOS))


def _draw_gradient(draw: ImageDraw.Draw, y_start: int, height: int, max_alpha: int = 200):
    for y in range(y_start, y_start + height):
        alpha = int(max_alpha * (y - y_start) / height)
        draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))


def _render_scene_frame(
    bg_frame: np.ndarray,
    text: str,
    scene_type: str,
    article_info: dict | None = None,
) -> np.ndarray:
    img = Image.fromarray(bg_frame).convert("RGBA")
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient at bottom
    _draw_gradient(draw, TARGET_H - 700, 700, max_alpha=210)

    # Article info bar at top for first scene
    if scene_type == "hook" and article_info:
        _draw_gradient(draw, 0, 200, max_alpha=160)
        # Flip the top gradient
        for y in range(200):
            alpha = int(160 * (200 - y) / 200)
            draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))

        font_sm = _get_font(32)
        font_journal = _get_font(38, bold=True)
        journal = article_info.get("journal", "")
        authors = article_info.get("authors", "")
        date = article_info.get("date", "")

        if journal:
            draw.text((60, 60), journal.upper(), font=font_journal, fill=(255, 255, 255, 230))
        if authors:
            draw.text((60, 110), authors, font=font_sm, fill=(200, 200, 200, 200))
        if date:
            draw.text((60, 150), date, font=font_sm, fill=(180, 180, 180, 180))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Main text
    font_size = 56 if scene_type in ("hook", "finding") else 48
    font = _get_font(font_size, bold=(scene_type == "hook"))
    wrapped = textwrap.fill(text, width=24)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (TARGET_W - tw) // 2
    y = TARGET_H - th - 250

    # Shadow
    draw.text((x + 3, y + 3), wrapped, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), wrapped, font=font, fill="white")

    return np.array(img.convert("RGB"))


def _build_scene_clip(
    image_path: Path,
    text: str,
    duration: float,
    scene_type: str,
    article_info: dict | None = None,
) -> ImageClip:
    base = _prepare_image(image_path)

    frames = []
    n_frames = int(duration * FPS)
    for i in range(n_frames):
        t = i / FPS
        bg = _ken_burns_frame(base, t, duration)
        frame = _render_scene_frame(bg, text, scene_type, article_info)
        frames.append(frame)

    return ImageSequenceClip(frames, fps=FPS)


def assemble_reel(
    scene_images: list[Path],
    audio_path: Path,
    scenes: list[dict],
    output_path: Path,
    article_info: dict | None = None,
) -> None:
    """Create multi-scene vertical Instagram Reel."""
    try:
        audio = AudioFileClip(str(audio_path))
        total_dur = min(audio.duration + 1.0, 59.0)
        n_scenes = len(scenes)
        per_scene = total_dur / n_scenes

        clips = []
        for i, scene in enumerate(scenes):
            img_path = scene_images[i] if i < len(scene_images) else scene_images[-1]
            info = article_info if i == 0 else None
            clip = _build_scene_clip(
                img_path, scene["text"], per_scene,
                scene.get("type", "context"), info,
            )
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio)

        video.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            verbose=False,
            logger=None,
        )
        print(f"Reel assembled: {output_path} ({total_dur:.1f}s, {n_scenes} scenes)")
    except Exception as e:
        print(f"MoviePy error: {e}")
        raise
