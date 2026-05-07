"""Assemble vertical reel video using MoviePy (image + text + audio)."""
from pathlib import Path
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip


def assemble_reel(
    image_path: Path,
    audio_path: Path,
    text: str,
    output_path: Path,
    duration: float = 45.0,
) -> None:
    """
    Create a vertical Instagram Reel (9:16 aspect, ~45s duration).
    Layers: image + text overlay + audio.
    """
    try:
        # Load audio to get exact duration
        audio = AudioFileClip(str(audio_path))
        duration = min(audio.duration, 59.0)  # Max 59s for IG Reels

        # Image clip (scaled to 1080x1920, center-cropped)
        img = ImageClip(str(image_path))
        img = img.resize(height=1920)
        if img.w > 1080:
            img = img.crop(width=1080)
        elif img.w < 1080:
            img = img.resize(width=1080)
        img = img.set_duration(duration)

        # Text overlay (bottom 1/3 of video)
        txt_clip = TextClip(
            text,
            fontsize=48,
            color="white",
            method="caption",
            size=(1000, 400),
            font="Arial",
            align="center",
        )
        txt_clip = txt_clip.set_position(("center", "bottom")).set_duration(duration)

        # Composite: image + text
        video = CompositeVideoClip([img, txt_clip])
        video = video.set_audio(audio)

        # Write to file
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
