"""Generate detailed multi-scene reel script using Google Gemini (English)."""
import json
import os
import random
import time
from google import genai


def write_reel(articles: list[dict]) -> tuple[dict, list[dict]]:
    """
    Pick one article and generate detailed scene breakdown.
    Returns (article, scenes) where each scene has text + image_query + type.
    """
    if not articles:
        return {}, _fallback_scenes({})

    # Prefer articles with abstracts and figures
    ranked = sorted(articles, key=lambda a: (
        len(a.get("abstract", "")) > 100,
        len(a.get("figure_urls", [])) > 0,
    ), reverse=True)
    article = ranked[0]

    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        return article, _fallback_scenes(article)

    client = genai.Client(api_key=api_key)
    abstract = article.get("abstract", "")[:2000]

    prompt = f"""You are a science communicator creating an Instagram Reel script.

ARTICLE:
Title: {article.get('title', 'Unknown')}
Journal: {article.get('journal', '')}
Authors: {article.get('authors', '')}
Abstract: {abstract}

Generate a JSON array of 5-6 scenes for a 30-45 second reel that explains this study.

Each scene must have:
- "text": narration text in English (20-35 words per scene)
- "image_query": English search term for background image (scientific, visual)
- "type": one of "hook", "background", "method", "finding", "impact", "cta"

Structure:
1. HOOK: Surprising question or bold statement about the finding
2. BACKGROUND: What problem were researchers trying to solve?
3. METHOD: How did they approach it? (simplified for general audience)
4. FINDING: What did they discover? (the key result)
5. IMPACT: Why does this matter? Real-world implications
6. CTA: Follow for more daily science

Rules:
- English only
- No jargon — explain like the audience is curious but not expert
- Each scene should stand alone visually
- Be specific about the findings, not generic
- image_query should be vivid and specific

Return ONLY the JSON array, no markdown."""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            raw = response.text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            scenes = json.loads(raw)
            if isinstance(scenes, list) and len(scenes) >= 4:
                return article, scenes
        except Exception as e:
            print(f"Gemini attempt {attempt + 1}/3: {e}")
            if attempt < 2:
                time.sleep(20)

    print("Gemini failed, using fallback scenes")
    return article, _fallback_scenes(article)


def _fallback_scenes(article: dict) -> list[dict]:
    """Build detailed scenes from article metadata + abstract."""
    title = article.get("title", "")
    journal = article.get("journal", "")
    authors = article.get("authors", "")
    abstract = article.get("abstract", "")
    topic = article.get("topic", "science")

    hooks = [
        "What if one study could change everything we know?",
        "Scientists just made a breakthrough you need to hear about.",
        "This discovery might reshape an entire field.",
        "A new study is challenging what we thought was true.",
    ]

    if not title or title.startswith("Article "):
        return [
            {"text": random.choice(hooks), "image_query": "science abstract", "type": "hook"},
            {"text": "New research is pushing the boundaries of what we know.", "image_query": "research lab modern", "type": "background"},
            {"text": "The findings could have far-reaching implications.", "image_query": "scientific breakthrough", "type": "finding"},
            {"text": "Follow for your daily dose of science.", "image_query": "science aesthetic", "type": "cta"},
        ]

    short_title = title[:150].rstrip(".")
    scenes = [
        {"text": random.choice(hooks), "image_query": f"{topic} abstract dark", "type": "hook"},
        {
            "text": f"Published in {journal}, a team led by {authors.split(',')[0] if authors else 'researchers'} investigated a critical question.",
            "image_query": "scientific journal publication",
            "type": "background",
        },
    ]

    # Try to extract method and finding from abstract
    if len(abstract) > 100:
        sentences = [s.strip() for s in abstract.replace(". ", ".\n").split("\n") if len(s.strip()) > 20]
        if len(sentences) >= 3:
            scenes.append({
                "text": _shorten(sentences[len(sentences) // 2], 120),
                "image_query": f"{topic} laboratory experiment",
                "type": "method",
            })
            scenes.append({
                "text": _shorten(sentences[-1], 120),
                "image_query": f"{topic} results data",
                "type": "finding",
            })
        else:
            scenes.append({
                "text": f"Their study: {short_title}.",
                "image_query": f"{topic} close up detail",
                "type": "finding",
            })
    else:
        scenes.append({
            "text": f"Their study: {short_title}.",
            "image_query": f"{topic} close up detail",
            "type": "finding",
        })

    scenes.append({
        "text": "This could open new doors for research and real-world applications.",
        "image_query": "innovation future science",
        "type": "impact",
    })
    scenes.append({
        "text": "Follow for your daily science breakdown.",
        "image_query": "science aesthetic minimal dark",
        "type": "cta",
    })

    return scenes


def _shorten(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "."
