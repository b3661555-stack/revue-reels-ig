"""Generate structured multi-scene reel script using Google Gemini."""
import json
import os
import random
import time
from google import genai


def write_reel(articles: list[dict]) -> tuple[dict, list[dict]]:
    """
    Pick one article and generate structured scenes.
    Returns (article, scenes) where each scene is:
      {"text": str, "image_query": str, "type": str}
    """
    if not articles:
        return {}, _fallback_scenes({})

    article = random.choice(articles)
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        return article, _fallback_scenes(article)

    client = genai.Client(api_key=api_key)

    prompt = f"""Generate a structured Instagram Reel script about this scientific article.
Title: {article.get('title', 'Unknown')}
Journal: {article.get('journal', '')}
Authors: {article.get('authors', '')}

Return ONLY a JSON array of 4-5 scenes. Each scene has:
- "text": the narration text in French (15-30 words per scene)
- "image_query": English search term for a background image
- "type": one of "hook", "context", "finding", "significance", "cta"

Example format:
[
  {{"text": "Et si votre cerveau pouvait apprendre même en dormant ?", "image_query": "brain neurons glowing", "type": "hook"}},
  {{"text": "Des chercheurs de Nature viennent de montrer que...", "image_query": "laboratory scientist microscope", "type": "context"}},
  {{"text": "Ils ont découvert que les neurones continuent...", "image_query": "neural network abstract", "type": "finding"}},
  {{"text": "Cela pourrait révolutionner le traitement de...", "image_query": "medical innovation future", "type": "significance"}},
  {{"text": "Suivez-nous pour plus de science au quotidien.", "image_query": "science aesthetic minimal", "type": "cta"}}
]

Rules:
- French language for text
- No hashtags, no emojis
- Hook must be a question or surprising statement
- Keep it accessible, no jargon
- image_query in English for Unsplash search"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            raw = response.text.strip()
            # Extract JSON from response
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            scenes = json.loads(raw)
            if isinstance(scenes, list) and len(scenes) >= 3:
                return article, scenes
        except Exception as e:
            print(f"Gemini attempt {attempt + 1}/3: {e}")
            if attempt < 2:
                time.sleep(20)

    print("Gemini failed, using fallback scenes")
    return article, _fallback_scenes(article)


def _fallback_scenes(article: dict) -> list[dict]:
    """Build structured scenes from article metadata."""
    title = article.get("title", "")
    journal = article.get("journal", "")
    topic = article.get("topic", "science")

    hooks = [
        "Et si cette découverte changeait tout ?",
        "La science vient de franchir un nouveau cap.",
        "Vous n'allez pas croire cette nouvelle étude.",
        "Une avancée qui pourrait tout transformer.",
    ]

    if title and not title.startswith("Article "):
        short_title = title[:100].rstrip(".")
        journal_mention = f"Publiée dans {journal}, " if journal else ""
        return [
            {"text": random.choice(hooks), "image_query": f"{topic} abstract", "type": "hook"},
            {"text": f"{journal_mention}une équipe de chercheurs a fait une découverte majeure.", "image_query": "scientific laboratory research", "type": "context"},
            {"text": f"{short_title}.", "image_query": f"{topic} close up", "type": "finding"},
            {"text": "Une avancée qui pourrait transformer notre compréhension.", "image_query": "innovation future technology", "type": "significance"},
            {"text": "Abonnez-vous pour la science au quotidien.", "image_query": "science aesthetic minimal", "type": "cta"},
        ]

    return [
        {"text": random.choice(hooks), "image_query": "science abstract colorful", "type": "hook"},
        {"text": "Chaque jour, la recherche fait des pas de géant.", "image_query": "research laboratory modern", "type": "context"},
        {"text": "De nouvelles découvertes changent notre vision du monde.", "image_query": "scientific breakthrough", "type": "finding"},
        {"text": "Suivez-nous pour ne rien manquer.", "image_query": "science aesthetic minimal", "type": "cta"},
    ]
