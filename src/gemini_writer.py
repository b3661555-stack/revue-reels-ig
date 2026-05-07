"""Generate short engaging text for Instagram Reels using Google Gemini."""
import os
import random
import time
from google import genai


HOOKS_FR = [
    "Saviez-vous que",
    "Une découverte incroyable",
    "La science vient de révéler",
    "Nouvelle étude surprenante",
    "Ce que la recherche nous apprend",
]


def _fallback_text(article: dict) -> str:
    """Build engaging text from article title when Gemini fails."""
    title = article.get("title", "")
    if not title or title.startswith("Article "):
        return "Une nouvelle découverte scientifique qui pourrait tout changer. Restez connectés pour en savoir plus."
    hook = random.choice(HOOKS_FR)
    short_title = title[:80].rstrip(".")
    return f"{hook} : {short_title}. Suivez-nous pour plus de science au quotidien."


def write_reel(articles: list[dict]) -> tuple[dict, str]:
    if not articles:
        return {}, "La science ne dort jamais. Nouvelles découvertes à suivre."

    article = random.choice(articles)
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        return article, _fallback_text(article)

    client = genai.Client(api_key=api_key)

    prompt = f"""Generate a short, engaging Instagram Reel script (30-50 words) about this article:
Title: {article.get('title', 'Unknown')}

Requirements:
- Start with a hook (question or intriguing statement)
- One key finding in simple language
- End with a call to action or wow moment
- French language
- Keep it punchy and visual
- No hashtags, no emojis"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip()
            if len(text) > 10:
                return article, text
        except Exception as e:
            print(f"Gemini attempt {attempt + 1}/3: {e}")
            if attempt < 2:
                time.sleep(20)

    print("Gemini failed after 3 attempts, using fallback")
    return article, _fallback_text(article)
