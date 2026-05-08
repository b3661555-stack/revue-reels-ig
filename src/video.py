"""Multi-scene vertical reel: Ken Burns, karaoke text, avatar overlay, PDF reveal."""
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

AVATAR_DIR = Path(__file__).resolve().parent.parent / "assets" / "avatar"
AVATAR_FPS = 12
AVATAR_DISPLAY_W, AVATAR_DISPLAY_H = 220, 212
AVATAR_MARGIN_R, AVATAR_MARGIN_B = 40, 80

HIGHLIGHT_BG = (255, 180, 30, 180)
SPOKEN_COLOR = (255, 255, 255, 255)
UNSPOKEN_COLOR = (180, 180, 180, 160)

_avatar_cache: list[Image.Image] | None = None


def _load_avatar_frames() -> list[Image.Image]:
    global _avatar_cache
    if _avatar_cache is not None:
        return _avatar_cache
    frames = []
    for i in range(1, 100):
        path = AVATAR_DIR / f"frame_{i:04d}.png"
        if not path.exists():
            break
        img = Image.open(path).convert("RGBA")
        img = img.resize((AVATAR_DISPLAY_W, AVATAR_DISPLAY_H), Image.LANCZOS)
        frames.append(img)
    _avatar_cache = frames if frames else None
    return frames


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


def _draw_top_gradient(draw: ImageDraw.Draw, height: int, max_alpha: int = 180):
    for y in range(height):
        alpha = int(max_alpha * (height - y) / height)
        draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))


def _draw_highlighted_text(
    draw: ImageDraw.Draw,
    overlay: Image.Image,
    text: str,
    t: float,
    duration: float,
    scene_type: str,
) -> None:
    """Draw text with word-by-word karaoke highlighting."""
    font_size = 54 if scene_type in ("hook", "finding") else 46
    is_bold = scene_type in ("hook", "finding")
    font = _get_font(font_size, bold=is_bold)
    space_w = font.getlength(" ")

    lines = textwrap.wrap(text, width=26)
    if not lines:
        return

    word_positions = []
    line_widths = []
    for line in lines:
        words = line.split()
        lw = sum(font.getlength(w) for w in words) + space_w * (len(words) - 1)
        line_widths.append(lw)
        for w in words:
            word_positions.append(w)

    total_words = len(word_positions)
    if total_words == 0:
        return

    start_t = 0.3
    end_t = max(duration - 0.5, start_t + 0.5)
    if t < start_t:
        current_idx = -1
    elif t >= end_t:
        current_idx = total_words
    else:
        progress = (t - start_t) / (end_t - start_t)
        current_idx = int(progress * total_words)

    line_height = int(font_size * 1.4)
    total_h = line_height * len(lines)
    base_y = TARGET_H - total_h - 200

    highlight_overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight_overlay)

    word_counter = 0
    for li, line in enumerate(lines):
        words = line.split()
        lw = line_widths[li]
        x = (TARGET_W - lw) / 2
        y = base_y + li * line_height

        for wi, word in enumerate(words):
            ww = font.getlength(word)
            global_idx = word_counter

            if global_idx == current_idx:
                pad_x, pad_y = 8, 4
                h_draw.rounded_rectangle(
                    [x - pad_x, y - pad_y, x + ww + pad_x, y + font_size + pad_y],
                    radius=6,
                    fill=HIGHLIGHT_BG,
                )
                for dx, dy in [(2, 2), (1, 1)]:
                    draw.text((x + dx, y + dy), word, font=font, fill=(0, 0, 0, 120))
                draw.text((x, y), word, font=font, fill="white")
            elif global_idx < current_idx:
                for dx, dy in [(2, 2), (1, 1)]:
                    draw.text((x + dx, y + dy), word, font=font, fill=(0, 0, 0, 120))
                draw.text((x, y), word, font=font, fill="white")
            else:
                draw.text((x, y), word, font=font, fill=(200, 200, 200))

            x += ww + space_w
            word_counter += 1

    overlay.paste(Image.alpha_composite(
        Image.new("RGBA", overlay.size, (0, 0, 0, 0)), highlight_overlay
    ), (0, 0), highlight_overlay)


def _render_scene_frame(
    bg_frame: np.ndarray,
    text: str,
    scene_type: str,
    t: float,
    duration: float,
    frame_number: int,
    article_info: dict | None = None,
    avatar_frames: list[Image.Image] | None = None,
) -> np.ndarray:
    img = Image.fromarray(bg_frame).convert("RGBA")
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    _draw_gradient(draw, TARGET_H - 750, 750, max_alpha=220)

    if article_info and article_info.get("journal"):
        _draw_top_gradient(draw, 220, max_alpha=180)
        font_journal = _get_font(36, bold=True)
        font_meta = _get_font(28)

        journal = article_info["journal"].upper()
        authors = article_info.get("authors", "")
        date = article_info.get("date", "")

        draw.text((60, 55), journal, font=font_journal, fill=(255, 255, 255, 240))
        meta_line = f"{authors}  |  {date}" if authors and date else (authors or date)
        if meta_line:
            draw.text((60, 100), meta_line, font=font_meta, fill=(200, 200, 200, 210))

        badges = {
            "hook": "THE QUESTION",
            "background": "BACKGROUND",
            "method": "THE APPROACH",
            "finding": "KEY FINDING",
            "impact": "WHY IT MATTERS",
            "cta": "FOLLOW FOR MORE",
            "paper": "NEW PAPER",
        }
        badge_text = badges.get(scene_type, "")
        if badge_text:
            font_badge = _get_font(24, bold=True)
            badge_w = draw.textlength(badge_text, font=font_badge) + 30
            badge_x, badge_y = 60, 155
            draw.rounded_rectangle(
                [badge_x, badge_y, badge_x + badge_w, badge_y + 36],
                radius=4, fill=(255, 100, 50, 200),
            )
            draw.text((badge_x + 15, badge_y + 5), badge_text, font=font_badge, fill="white")

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    _draw_highlighted_text(draw, img, text, t, duration, scene_type)

    if avatar_frames:
        avatar_idx = (frame_number // (FPS // AVATAR_FPS)) % len(avatar_frames)
        avatar_img = avatar_frames[avatar_idx]
        ax = TARGET_W - AVATAR_DISPLAY_W - AVATAR_MARGIN_R
        ay = TARGET_H - AVATAR_DISPLAY_H - AVATAR_MARGIN_B
        img.paste(avatar_img, (ax, ay), avatar_img)

    return np.array(img.convert("RGB"))


def _render_paper_frame(
    pdf_image: Image.Image,
    text: str,
    t: float,
    duration: float,
    frame_number: int,
    article_info: dict | None = None,
    avatar_frames: list[Image.Image] | None = None,
) -> np.ndarray:
    """Render opening paper reveal scene."""
    img = Image.new("RGBA", (TARGET_W, TARGET_H), (20, 20, 40, 255))

    progress = t / max(duration, 0.1)
    zoom = 1.15 - 0.15 * progress
    pw = int(700 * zoom)
    ph = int(pw * pdf_image.height / pdf_image.width)
    paper = pdf_image.resize((pw, ph), Image.LANCZOS)

    px = (TARGET_W - pw) // 2
    py = max(200, (TARGET_H - ph) // 2 - 100)

    shadow = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 80))
    img.paste(shadow, (px + 10, py + 10), shadow)

    border = Image.new("RGBA", (pw + 8, ph + 8), (255, 255, 255, 200))
    img.paste(border, (px - 4, py - 4), border)

    if paper.mode != "RGBA":
        paper = paper.convert("RGBA")
    img.paste(paper, (px, py), paper)

    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _draw_gradient(draw, TARGET_H - 500, 500, max_alpha=230)

    if article_info and article_info.get("journal"):
        _draw_top_gradient(draw, 180, max_alpha=160)
        font_journal = _get_font(36, bold=True)
        draw.text((60, 55), article_info["journal"].upper(), font=font_journal, fill=(255, 255, 255, 240))
        font_badge = _get_font(24, bold=True)
        badge_text = "NEW PAPER"
        badge_w = draw.textlength(badge_text, font=font_badge) + 30
        draw.rounded_rectangle([60, 105, 60 + badge_w, 141], radius=4, fill=(255, 100, 50, 200))
        draw.text((75, 110), badge_text, font=font_badge, fill="white")

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    font = _get_font(42, bold=True)
    wrapped = textwrap.fill(text, width=30)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (TARGET_W - tw) // 2
    ty = TARGET_H - th - 160
    for dx, dy in [(3, 3), (2, 2)]:
        draw.text((tx + dx, ty + dy), wrapped, font=font, fill=(0, 0, 0, 150))
    draw.text((tx, ty), wrapped, font=font, fill="white")

    if avatar_frames:
        avatar_idx = (frame_number // (FPS // AVATAR_FPS)) % len(avatar_frames)
        ax = TARGET_W - AVATAR_DISPLAY_W - AVATAR_MARGIN_R
        ay = TARGET_H - AVATAR_DISPLAY_H - AVATAR_MARGIN_B
        img.paste(avatar_frames[avatar_idx], (ax, ay), avatar_frames[avatar_idx])

    return np.array(img.convert("RGB"))


def _build_scene_clip(
    image_path: Path,
    text: str,
    duration: float,
    scene_type: str,
    article_info: dict | None = None,
    avatar_frames: list[Image.Image] | None = None,
    global_frame_offset: int = 0,
    pdf_page_image: Image.Image | None = None,
) -> tuple[ImageSequenceClip, int]:
    n_frames = int(duration * FPS)

    if scene_type == "paper" and pdf_page_image is not None:
        frames = []
        for i in range(n_frames):
            t = i / FPS
            frame = _render_paper_frame(
                pdf_page_image, text, t, duration,
                global_frame_offset + i, article_info, avatar_frames,
            )
            frames.append(frame)
        return ImageSequenceClip(frames, fps=FPS), global_frame_offset + n_frames

    base = _prepare_image(image_path)
    frames = []
    for i in range(n_frames):
        t = i / FPS
        bg = _ken_burns_frame(base, t, duration)
        frame = _render_scene_frame(
            bg, text, scene_type, t, duration,
            global_frame_offset + i, article_info, avatar_frames,
        )
        frames.append(frame)
    return ImageSequenceClip(frames, fps=FPS), global_frame_offset + n_frames


def assemble_reel(
    scene_images: list[Path],
    audio_path: Path,
    scenes: list[dict],
    output_path: Path,
    article_info: dict | None = None,
    pdf_page_image_path: Path | None = None,
) -> None:
    """Create multi-scene vertical Instagram Reel."""
    try:
        avatar_frames = _load_avatar_frames()
        if not avatar_frames:
            print("  No avatar frames found, continuing without avatar")
            avatar_frames = None

        pdf_img = None
        if pdf_page_image_path and pdf_page_image_path.exists():
            pdf_img = Image.open(pdf_page_image_path).convert("RGBA")

        audio = AudioFileClip(str(audio_path))
        total_dur = min(audio.duration + 1.5, 59.0)
        n_scenes = len(scenes)

        paper_dur = 3.5 if any(s.get("type") == "paper" for s in scenes) else 0
        remaining = total_dur - paper_dur
        narrative_count = sum(1 for s in scenes if s.get("type") != "paper")
        per_scene = remaining / max(narrative_count, 1)

        clips = []
        frame_offset = 0
        for i, scene in enumerate(scenes):
            img_path = scene_images[i] if i < len(scene_images) else scene_images[-1]
            dur = paper_dur if scene.get("type") == "paper" else per_scene

            clip, frame_offset = _build_scene_clip(
                img_path, scene["text"], dur,
                scene.get("type", "context"), article_info,
                avatar_frames, frame_offset,
                pdf_img if scene.get("type") == "paper" else None,
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
