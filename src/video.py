"""Multi-scene vertical reel: Ken Burns, karaoke text, avatar overlay, paper reveal."""
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
AVATAR_DISPLAY_W, AVATAR_DISPLAY_H = 280, 380
AVATAR_MARGIN_R = 30

HIGHLIGHT_BG = (255, 180, 30, 180)

_avatar_cache: list[Image.Image] | None = None


def _load_avatar_frames() -> list[Image.Image]:
    global _avatar_cache
    if _avatar_cache is not None:
        return _avatar_cache
    frames = []
    for i in range(1, 1000):
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


def _paste_avatar(img: Image.Image, frame_number: int, avatar_frames: list[Image.Image] | None):
    if not avatar_frames:
        return
    avatar_idx = (frame_number // max(1, FPS // AVATAR_FPS)) % len(avatar_frames)
    avatar_img = avatar_frames[avatar_idx]
    ax = TARGET_W - AVATAR_DISPLAY_W - AVATAR_MARGIN_R
    ay = TARGET_H - AVATAR_DISPLAY_H
    img.paste(avatar_img, (ax, ay), avatar_img)


def _draw_highlighted_text(
    draw: ImageDraw.Draw,
    overlay: Image.Image,
    text: str,
    t: float,
    duration: float,
    scene_type: str,
) -> None:
    """Draw text with word-by-word karaoke highlighting, max 2 lines visible."""
    font_size = 48 if scene_type in ("hook", "finding") else 42
    is_bold = scene_type in ("hook", "finding")
    font = _get_font(font_size, bold=is_bold)
    space_w = font.getlength(" ")

    words = text.split()
    if not words:
        return

    total_words = len(words)
    start_t = 0.2
    end_t = max(duration - 0.3, start_t + 0.5)
    if t < start_t:
        current_idx = 0
    elif t >= end_t:
        current_idx = total_words - 1
    else:
        progress = (t - start_t) / (end_t - start_t)
        current_idx = min(int(progress * total_words), total_words - 1)

    max_line_w = TARGET_W - 120
    visible_lines = []
    line_words = []
    line_w = 0.0
    word_to_global = []

    for gi, w in enumerate(words):
        ww = font.getlength(w)
        test_w = line_w + (space_w if line_words else 0) + ww
        if test_w > max_line_w and line_words:
            visible_lines.append(line_words)
            line_words = [w]
            line_w = ww
        else:
            line_words.append(w)
            line_w = test_w
        word_to_global.append(gi)
    if line_words:
        visible_lines.append(line_words)

    current_line_idx = 0
    counter = 0
    for li, lwords in enumerate(visible_lines):
        if counter + len(lwords) > current_idx:
            current_line_idx = li
            break
        counter += len(lwords)

    show_start = max(0, current_line_idx - 1)
    show_end = min(len(visible_lines), show_start + 3)
    if show_end - show_start < 3 and show_start > 0:
        show_start = max(0, show_end - 3)

    displayed_lines = visible_lines[show_start:show_end]
    line_height = int(font_size * 1.5)
    total_h = line_height * len(displayed_lines)
    base_y = TARGET_H - total_h - 420

    highlight_overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight_overlay)

    global_counter = sum(len(visible_lines[i]) for i in range(show_start))

    for li, lwords in enumerate(displayed_lines):
        lw = sum(font.getlength(w) for w in lwords) + space_w * max(0, len(lwords) - 1)
        x = (TARGET_W - lw) / 2
        y = base_y + li * line_height

        for w in lwords:
            ww = font.getlength(w)
            if global_counter == current_idx:
                pad_x, pad_y = 8, 4
                h_draw.rounded_rectangle(
                    [x - pad_x, y - pad_y, x + ww + pad_x, y + font_size + pad_y],
                    radius=6, fill=HIGHLIGHT_BG,
                )
                for dx, dy in [(2, 2)]:
                    draw.text((x + dx, y + dy), w, font=font, fill=(0, 0, 0, 120))
                draw.text((x, y), w, font=font, fill="white")
            elif global_counter < current_idx:
                for dx, dy in [(2, 2)]:
                    draw.text((x + dx, y + dy), w, font=font, fill=(0, 0, 0, 120))
                draw.text((x, y), w, font=font, fill="white")
            else:
                draw.text((x, y), w, font=font, fill=(180, 180, 180))

            x += ww + space_w
            global_counter += 1

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
            "hook": "BREAKING",
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
    _paste_avatar(img, frame_number, avatar_frames)

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

    font = _get_font(40, bold=True)
    wrapped = textwrap.fill(text, width=32)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (TARGET_W - tw) // 2
    ty = TARGET_H - th - 160
    for dx, dy in [(3, 3), (2, 2)]:
        draw.text((tx + dx, ty + dy), wrapped, font=font, fill=(0, 0, 0, 150))
    draw.text((tx, ty), wrapped, font=font, fill="white")

    _paste_avatar(img, frame_number, avatar_frames)

    return np.array(img.convert("RGB"))


def _render_synthetic_paper(article_info: dict) -> Image.Image:
    """Render a synthetic A4 paper page from article metadata."""
    w, h = 1654, 2339
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_title = _get_font(56, bold=True)
    font_authors = _get_font(36)
    font_journal = _get_font(32, bold=True)
    font_abstract = _get_font(30)

    y = 160
    journal = article_info.get("journal", "").upper()
    if journal:
        jw = draw.textlength(journal, font=font_journal)
        draw.text(((w - jw) / 2, y), journal, font=font_journal, fill=(180, 40, 40))
        y += 80
        draw.line([(100, y), (w - 100, y)], fill=(180, 40, 40), width=3)
        y += 50

    title = article_info.get("title", "")
    if title:
        wrapped = textwrap.fill(title, width=45)
        bbox = draw.textbbox((0, 0), wrapped, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y), wrapped, font=font_title, fill=(30, 30, 30))
        th = bbox[3] - bbox[1]
        y += th + 50

    authors = article_info.get("authors", "")
    if authors:
        aw = draw.textlength(authors, font=font_authors)
        draw.text(((w - aw) / 2, y), authors, font=font_authors, fill=(80, 80, 80))
        y += 60

    date = article_info.get("date", "")
    if date:
        dw = draw.textlength(date, font=font_authors)
        draw.text(((w - dw) / 2, y), date, font=font_authors, fill=(120, 120, 120))
        y += 80

    draw.line([(100, y), (w - 100, y)], fill=(200, 200, 200), width=2)
    y += 40

    abstract = article_info.get("abstract", "")
    if abstract:
        draw.text((120, y), "ABSTRACT", font=font_journal, fill=(60, 60, 60))
        y += 60
        para = textwrap.fill(abstract[:800], width=70)
        draw.text((120, y), para, font=font_abstract, fill=(40, 40, 40))

    return img


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
        elif article_info and any(s.get("type") == "paper" for s in scenes):
            synth = _render_synthetic_paper({
                **(article_info or {}),
                "title": next((s["text"] for s in scenes if s.get("type") == "paper"), ""),
                "abstract": article_info.get("abstract", "") if article_info else "",
            })
            pdf_img = synth.convert("RGBA")

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
