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

    prompt = f"""You are a science communicator creating an Instagram Reel script about a major research breakthrough.

ARTICLE:
Title: {article.get('title', 'Unknown')}
Journal: {article.get('journal', '')}
Authors: {article.get('authors', '')}
Abstract: {abstract}

Generate a JSON array of 5-6 scenes for a 45-55 second reel that explains this study in depth.

Each scene must have:
- "text": narration text in English (25-40 words per scene, exactly 1-2 complete sentences)
- "image_query": English search term for background image (scientific, vivid, specific)
- "type": one of "hook", "background", "method", "finding", "impact", "cta"

Structure:
1. HOOK: Start with a specific number, statistic, or surprising fact from the study. Never a generic question. Name the organism, drug, protein, or population.
2. BACKGROUND: What problem were researchers trying to solve? Be concrete about the gap in knowledge.
3. METHOD: How did they approach it? Name the technique or model system. Simplified but specific.
4. FINDING: The key result with numbers or magnitudes when available. This is the climax.
5. IMPACT: Real-world implications. Who benefits? What changes? Be concrete.
6. CTA: Reference the specific topic area (e.g. "Follow for more on cancer immunotherapy" not "follow for science").

Rules:
- English only, active voice throughout
- No jargon but use proper scientific terms with brief context
- Every sentence must be COMPLETE (never cut mid-phrase)
- Match the tone to the significance: major breakthroughs deserve energy and conviction
- Be specific about findings, never generic platitudes
- image_query should be vivid and specific to the scene content

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

    if not title or title.startswith("Article "):
        return [
            {"text": "A remarkable new study just dropped. Here is what you need to know.", "image_query": "science abstract", "type": "hook"},
            {"text": "Researchers tackled a question at the frontier of current knowledge.", "image_query": "research lab modern", "type": "background"},
            {"text": "Their findings could reshape how we understand this field.", "image_query": "scientific breakthrough", "type": "finding"},
            {"text": "Follow for your daily science breakdown.", "image_query": "science aesthetic", "type": "cta"},
        ]

    short_title = _shorten(title, 120)
    lead_author = authors.split(",")[0].strip() if authors else "researchers"

    scenes = [
        {
            "text": f"A new study in {journal} reveals something striking about {short_title.lower().rstrip('.')}.",
            "image_query": f"{topic} abstract dark",
            "type": "hook",
        },
        {
            "text": f"A team led by {lead_author} set out to answer a fundamental question in {topic}.",
            "image_query": "scientific journal publication",
            "type": "background",
        },
    ]

    if len(abstract) > 100:
        sentences = [s.strip() for s in abstract.replace(". ", ".\n").split("\n") if len(s.strip()) > 30]
        if len(sentences) >= 3:
            scenes.append({
                "text": _shorten(sentences[len(sentences) // 2], 160),
                "image_query": f"{topic} laboratory experiment",
                "type": "method",
            })
            scenes.append({
                "text": _shorten(sentences[-1], 160),
                "image_query": f"{topic} results data",
                "type": "finding",
            })
        elif len(sentences) >= 1:
            scenes.append({
                "text": _shorten(sentences[-1], 160),
                "image_query": f"{topic} close up detail",
                "type": "finding",
            })
        else:
            scenes.append({
                "text": f"Their investigation: {short_title}.",
                "image_query": f"{topic} close up detail",
                "type": "finding",
            })
    else:
        scenes.append({
            "text": f"Their investigation: {short_title}.",
            "image_query": f"{topic} close up detail",
            "type": "finding",
        })

    scenes.append({
        "text": f"This research could open new avenues for {topic} and have real-world impact.",
        "image_query": "innovation future science",
        "type": "impact",
    })
    scenes.append({
        "text": f"Follow for more breakthroughs in {topic}.",
        "image_query": "science aesthetic minimal dark",
        "type": "cta",
    })

    return scenes


def _shorten(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    for end in ['. ', '? ', '! ']:
        idx = text.rfind(end, 0, max_len)
        if idx > max_len // 3:
            return text[:idx + 1].strip()
    cut = text[:max_len].rsplit(" ", 1)[0]
    if len(cut) < max_len // 3:
        cut = text[:max_len]
    return cut.rstrip(",.;:- ") + "."
