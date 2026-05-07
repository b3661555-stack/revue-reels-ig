"""Orchestrator: gather → write → fetch images → synthesize → video → upload → post IG."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
except ImportError:
    pass

from src import pubmed, gemini_writer, images, audio, video, instagram


def _local_now():
    tz = os.environ.get("REEL_TIMEZONE", "Europe/Zurich")
    return datetime.now(ZoneInfo(tz))


def run() -> None:
    now = _local_now()
    today_iso = now.strftime("%Y-%m-%d")
    today_fr = now.strftime("%d/%m/%Y")
    print(f"=== Revue Reels IG — {today_fr} ===")

    # 1) Gather PubMed
    print("[1/6] PubMed...")
    pm_data = pubmed.gather_all(days_back=3)
    print(f"      articles found: {len(pm_data)}")

    # 2) Generate short text + pick article for reel
    print("[2/6] Gemini text generation...")
    article, reel_text = gemini_writer.write_reel(pm_data)
    print(f"      text length: {len(reel_text)} chars")
    if article.get("title"):
        print(f"      article: {article['title'][:60]}...")

    # 3) Fetch scientific image
    print("[3/6] Unsplash image...")
    with tempfile.TemporaryDirectory() as td:
        image_path = Path(td) / f"reel_{today_iso}.jpg"
        images.fetch_for_topic(article.get("topic", "science"), image_path)
        print(f"      image: {image_path.name}")

        # 4) Synthesize audio + mix with music
        print("[4/6] Azure TTS + music...")
        audio_path = Path(td) / f"reel_{today_iso}.wav"
        audio.synthesize_with_music(reel_text, audio_path)
        print(f"      audio ready: {audio_path.name}")

        # 5) Assemble video (MoviePy)
        print("[5/6] MoviePy assembly...")
        reel_path = Path(td) / f"reel_{today_iso}.mp4"
        video.assemble_reel(image_path, audio_path, reel_text, reel_path)
        print(f"      video ready: {reel_path.name}")

        # Copy to workspace root for GH Actions artifact
        import shutil
        final_reel = Path(f"reel_{today_iso}.mp4")
        shutil.copy2(reel_path, final_reel)

        # 6) Post to Instagram
        print("[6/6] Instagram posting...")
        if os.environ.get("INSTAGRAM_USERNAME"):
            try:
                instagram.post_reel(reel_path, reel_text)
                print(f"      posted to @{os.environ.get('INSTAGRAM_USERNAME')}")
            except Exception as e:
                print(f"      [instagram] FAILED (non-fatal): {e}")
        else:
            print("[instagram] INSTAGRAM_USERNAME not set, skip")

    print("=== OK ===")


if __name__ == "__main__":
    run()
