"""Generate short engaging text for Instagram Reels using Google Gemini."""
import os
import random
from google import genai


def write_reel(articles: list[dict]) -> tuple[dict, str]:
    """
    Pick one article and generate short, engaging reel text (30-50 words).
    Returns (article, reel_text).
    """
    if not articles:
        return {}, "Science news coming soon."

    article = random.choice(articles)
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        return article, "Latest scientific discovery."

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Generate a short, engaging Instagram Reel script (30-50 words) about this article:
    Title: {article.get('title', 'Unknown')}

    Requirements:
    - Start with a hook (question or intriguing statement)
    - One key finding in simple language
    - End with a call to action or wow moment
    - French language
    - Keep it punchy and visual
    """

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        return article, response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return article, "Découverte scientifique fascinante."
