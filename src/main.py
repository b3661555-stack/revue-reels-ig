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

    # 2b) Fetch article preview: og:image from DOI, then PDF, then synthetic fallback
    paper_image_path = None
    doi = article.get("doi", "")
    pmcid = article.get("pmcid", "")

    if doi:
        print("[2b] Article preview via DOI...")
        with tempfile.TemporaryDirectory() as prev_td:
            prev_img = Path(prev_td) / "preview.jpg"
            if pubmed.fetch_article_preview(doi, prev_img):
                stable = Path(tempfile.gettempdir()) / "article_preview.jpg"
                shutil.copy2(prev_img, stable)
                paper_image_path = stable
                print(f"      Preview ready (og:image)")

    if not paper_image_path and pmcid:
        print("[2b] PDF fetch fallback...")
        with tempfile.TemporaryDirectory() as pdf_td:
            pdf_file = Path(pdf_td) / "article.pdf"
            if pubmed.fetch_pdf(pmcid, pdf_file):
                pdf_img = Path(pdf_td) / "pdf_page1.png"
                if images.render_pdf_page1(pdf_file, pdf_img):
                    stable = Path(tempfile.gettempdir()) / "pdf_page1.png"
                    shutil.copy2(pdf_img, stable)
                    paper_image_path = stable
                    print(f"      PDF page 1 ready")

    # Always add paper scene at start (synthetic if no real preview/PDF)
    scenes.insert(0, {
        "text": article.get("title", "New Study"),
        "type": "paper",
        "image_query": "",
    })

    # 2c) Extract abstract passages for dynamic text overlay
    abstract_text = article.get("abstract", "")
    if abstract_text:
        sentences = [s.strip() for s in abstract_text.replace(". ", ".\n").split("\n")
                     if len(s.strip()) > 30]
        if len(sentences) >= 3:
            for sc in scenes:
                if sc.get("type") == "method" and "passage" not in sc:
                    sc["passage"] = sentences[len(sentences) // 2][:200]
                elif sc.get("type") == "finding" and "passage" not in sc:
                    sc["passage"] = sentences[-1][:200]
        elif len(sentences) >= 1:
            for sc in scenes:
                if sc.get("type") == "finding" and "passage" not in sc:
                    sc["passage"] = sentences[-1][:200]

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

        # 4) TTS — concatenate all scene texts (skip paper scene)
        print("[4/6] Azure TTS...")
        narration_scenes = [s for s in scenes if s.get("type") != "paper"]
        full_narration = " ... ".join(s["text"] for s in narration_scenes)
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
            "title": article.get("title", ""),
            "abstract": article.get("abstract", ""),
        }
        video.assemble_reel(
            scene_images, audio_path, scenes, reel_path,
            article_info, paper_image_path,
        )
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
