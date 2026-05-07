"""Assemble vertical reel video using MoviePy (image + text via Pillow)."""
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip


def _compose_frame(image_path: Path, text: str) -> str:
    """Create 1080x1920 image with text overlay, return temp path."""
    img = Image.open(image_path).convert("RGB")

    # Scale to fill 1080x1920
    target_w, target_h = 1080, 1920
    scale = max(target_w / img.width, target_h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

    # Center crop
    left = (img.width - target_w) // 2
    top = (img.height - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    # Semi-transparent overlay at bottom
    overlay = Image.new("RGBA", (target_w, 500), (0, 0, 0, 160))
    img = img.convert("RGBA")
    img.paste(overlay, (0, target_h - 500), overlay)

    # Draw text
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 46)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 46)
        except OSError:
            font = ImageFont.load_default()

    wrapped = textwrap.fill(text, width=30)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (target_w - tw) // 2
    y = target_h - 450 + (400 - th) // 2
    draw.text((x, y), wrapped, font=font, fill="white")

    out = str(image_path).replace(".jpg", "_composed.png")
    img.convert("RGB").save(out)
    return out


def assemble_reel(
    image_path: Path,
    audio_path: Path,
    text: str,
    output_path: Path,
    duration: float = 45.0,
) -> None:
    """Create a vertical Instagram Reel (9:16 aspect, ~45s duration)."""
    try:
        audio = AudioFileClip(str(audio_path))
        duration = min(audio.duration, 59.0)

        composed = _compose_frame(image_path, text)
        img = ImageClip(composed).set_duration(duration)

        video = CompositeVideoClip([img])
        video = video.set_audio(audio)

        video.write_videofile(
            str(output_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        print(f"Reel assembled: {output_path}")
    except Exception as e:
        print(f"MoviePy error: {e}")
        raise
