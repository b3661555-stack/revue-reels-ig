"""Orchestrator: PubMed → Gemini scenes → images → TTS → video → Instagram."""
from __future__ import annotations

import os
import sys
import shutil
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

    # 1) PubMed
    print("[1/6] PubMed...")
    pm_data = pubmed.gather_all(days_back=3)
    print(f"      articles: {len(pm_data)}")

    # 2) Gemini → structured scenes
    print("[2/6] Gemini scenes...")
    article, scenes = gemini_writer.write_reel(pm_data)
    print(f"      scenes: {len(scenes)}")
    if article.get("title"):
        print(f"      article: {article['title'][:60]}...")
    for i, s in enumerate(scenes):
        print(f"        [{s.get('type', '?')}] {s['text'][:50]}...")

    # 3) Fetch images (one per scene)
    print("[3/6] Images...")
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        scene_images = images.fetch_scene_images(
            scenes,
            article.get("figure_urls", []),
            td_path,
        )
        print(f"      images: {len(scene_images)}")

        # 4) TTS — concatenate all scene texts
        print("[4/6] Azure TTS...")
        full_narration = " ... ".join(s["text"] for s in scenes)
        audio_path = td_path / f"reel_{today_iso}.wav"
        audio.synthesize_with_music(full_narration, audio_path)
        print(f"      audio ready")

        # 5) Multi-scene video
        print("[5/6] Video assembly...")
        reel_path = td_path / f"reel_{today_iso}.mp4"
        article_info = {
            "journal": article.get("journal", ""),
            "authors": article.get("authors", ""),
            "date": article.get("date", ""),
        }
        video.assemble_reel(scene_images, audio_path, scenes, reel_path, article_info)
        print(f"      video ready")

        # Copy for artifact
        final_reel = Path(f"reel_{today_iso}.mp4")
        shutil.copy2(reel_path, final_reel)

        # 6) Instagram
        print("[6/6] Instagram...")
        if os.environ.get("INSTAGRAM_USERNAME"):
            caption = (
                f"{article.get('title', 'Science du jour')}\n\n"
                f"{article.get('journal', '')} | {article.get('authors', '')}\n\n"
                "#science #research #pubmed #dailyscience"
            )
            try:
                instagram.post_reel(final_reel, caption)
                print(f"      posted to @{os.environ.get('INSTAGRAM_USERNAME')}")
            except Exception as e:
                print(f"      [ig] FAILED (non-fatal): {e}")
        else:
            print("      [ig] skip (no credentials)")

    print("=== OK ===")


if __name__ == "__main__":
    run()
