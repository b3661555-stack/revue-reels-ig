# Revue Reels IG

Automated daily Instagram Reels generator for scientific content.

## Architecture

Cron daily via GitHub Actions:
1. PubMed E-utilities → fetch articles
2. Google Gemini → generate short text
3. Unsplash API → fetch scientific images
4. MoviePy → assemble vertical video (9:16) + overlay text
5. Azure TTS Vivienne → synthesize narration + background music
6. instagrapi → post to Instagram

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

## Test locally

```bash
python -m src.main --dry-run
```

## Project structure

```
src/
  main.py              orchestrator
  pubmed.py            article fetching
  gemini_writer.py     text generation
  images.py            Unsplash image fetching
  video.py             MoviePy video assembly
  audio.py             Azure TTS + music mixing
  instagram.py         instagrapi posting
```
