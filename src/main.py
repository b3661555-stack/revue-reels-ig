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

    # 2b) Acquire real paper: Unpaywall PDF → PMC PDF → og:image → synthetic
    paper_image_path = None
    pdf_figure_paths: list[Path] = []
    doi = article.get("doi", "")
    pmcid = article.get("pmcid", "")
    stable_pdf = Path(tempfile.gettempdir()) / "article.pdf"
    pdf_ok = False

    if doi:
        print("[2b] Unpaywall PDF...")
        pdf_ok = pubmed.fetch_pdf_via_unpaywall(doi, stable_pdf)

    if not pdf_ok and pmcid:
        print("[2b] PMC PDF fallback...")
        pdf_ok = pubmed.fetch_pdf(pmcid, stable_pdf)

    if pdf_ok:
        page1_img = Path(tempfile.gettempdir()) / "pdf_page1.png"
        if images.render_pdf_page1(stable_pdf, page1_img):
            paper_image_path = page1_img
            print(f"      Paper page 1 ready (real PDF)")
        figs_dir = Path(tempfile.gettempdir()) / "pdf_figures"
        figs_dir.mkdir(exist_ok=True)
        pdf_figure_paths = images.extract_figures_from_pdf(stable_pdf, figs_dir)

    if not paper_image_path and doi:
        print("[2b] og:image fallback...")
        prev_img = Path(tempfile.gettempdir()) / "article_preview.jpg"
        if pubmed.fetch_article_preview(doi, prev_img):
            paper_image_path = prev_img
            print(f"      Preview ready (og:image)")

    # Always add paper scene at start (synthetic if nothing else)
    scenes.insert(0, {
        "text": article.get("title", "New Study"),
        "type": "paper",
        "image_query": "",
    })

    # 2c) Extract abstract passages — voice reads them, paper as background
    abstract_text = article.get("abstract", "")
    if abstract_text and paper_image_path:
        sentences = [s.strip() for s in abstract_text.replace(". ", ".\n").split("\n")
                     if len(s.strip()) > 30]
        if len(sentences) >= 3:
            for sc in scenes:
                if sc.get("type") == "method":
                    raw = sentences[len(sentences) // 2]
                    sc["text"] = gemini_writer._depersonalize(
                        gemini_writer._shorten(raw, 120))
                    sc["use_paper_bg"] = True
                elif sc.get("type") == "finding":
                    raw = sentences[-1]
                    sc["text"] = gemini_writer._depersonalize(
                        gemini_writer._shorten(raw, 120))
                    sc["use_paper_bg"] = True
        elif len(sentences) >= 1:
            for sc in scenes:
                if sc.get("type") == "finding":
                    raw = sentences[-1]
                    sc["text"] = gemini_writer._depersonalize(
                        gemini_writer._shorten(raw, 120))
                    sc["use_paper_bg"] = True

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

        # Override images: passage scenes → paper, finding/method → PDF figures
        fig_used = 0
        for i, sc in enumerate(scenes):
            if i >= len(scene_images):
                break
            if sc.get("use_paper_bg") and paper_image_path:
                shutil.copy2(paper_image_path, scene_images[i])
                print(f"      scene_{i}: paper background ({sc.get('type')})")
            elif sc.get("type") in ("finding", "method") and fig_used < len(pdf_figure_paths):
                shutil.copy2(pdf_figure_paths[fig_used], scene_images[i])
                print(f"      scene_{i}: PDF figure {fig_used}")
                fig_used += 1

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
            "doi": article.get("doi", ""),
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
