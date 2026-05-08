"""Generate detailed multi-scene reel script using Google Gemini (English)."""
import json
import os
import time
from google import genai


def write_reel(articles: list[dict]) -> tuple[dict, list[dict]]:
    """
    Pick one article and generate detailed scene breakdown.
    Returns (article, scenes) where each scene has text + image_query + type.
    """
    if not articles:
        return {}, _fallback_scenes({})

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

Generate a JSON array of 6 scenes for a 50-second reel. Each scene is narrated over ~8 seconds.

Each scene must have:
- "text": narration text in English. SHORT: 12-20 words max per scene. 1 sentence only.
- "image_query": vivid English search term for background image
- "type": one of "hook", "background", "method", "finding", "impact", "cta"

Structure:
1. HOOK: A bold, specific statement. Lead with a number or surprising fact. Name the subject.
2. BACKGROUND: What gap in knowledge did researchers address? Be concrete.
3. METHOD: Name the technique. One sentence, simplified but specific.
4. FINDING: The key result. Include a number or magnitude. This is the climax.
5. IMPACT: Who benefits? What changes? One concrete implication.
6. CTA: "Follow for more on [specific topic]."

CRITICAL RULES:
- Third person only. Say "researchers found" or "the team discovered", NEVER "we".
- 12-20 words per scene, never more. Short punchy sentences.
- Every sentence must be COMPLETE. Never cut mid-phrase.
- Active voice. Specific. No generic platitudes.
- No jargon without context. Use proper scientific terms briefly explained.

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
            {"text": "A groundbreaking study just dropped. Here is what it found.", "image_query": "science abstract", "type": "hook"},
            {"text": "Researchers tackled a question at the frontier of current knowledge.", "image_query": "research lab modern", "type": "background"},
            {"text": "Their findings could reshape how scientists understand this field.", "image_query": "scientific breakthrough", "type": "finding"},
            {"text": "Follow for daily science breakthroughs.", "image_query": "science aesthetic", "type": "cta"},
        ]

    short_title = _shorten(title, 80)
    lead_author = authors.split(",")[0].strip() if authors else "a research team"

    scenes = [
        {
            "text": f"New in {journal}: a discovery about {short_title.lower().rstrip('.')}.",
            "image_query": f"{topic} abstract dark",
            "type": "hook",
        },
        {
            "text": f"{lead_author} and colleagues set out to solve a key problem in {topic}.",
            "image_query": "scientific journal publication",
            "type": "background",
        },
    ]

    if len(abstract) > 100:
        sentences = [s.strip() for s in abstract.replace(". ", ".\n").split("\n") if len(s.strip()) > 30]
        if len(sentences) >= 3:
            method_sent = _depersonalize(_shorten(sentences[len(sentences) // 2], 100))
            finding_sent = _depersonalize(_shorten(sentences[-1], 100))
            scenes.append({
                "text": method_sent,
                "image_query": f"{topic} laboratory experiment",
                "type": "method",
            })
            scenes.append({
                "text": finding_sent,
                "image_query": f"{topic} results data",
                "type": "finding",
            })
        elif len(sentences) >= 1:
            scenes.append({
                "text": _depersonalize(_shorten(sentences[-1], 100)),
                "image_query": f"{topic} close up detail",
                "type": "finding",
            })
        else:
            scenes.append({
                "text": f"The study examined {short_title.lower().rstrip('.')}.",
                "image_query": f"{topic} close up detail",
                "type": "finding",
            })
    else:
        scenes.append({
            "text": f"The study examined {short_title.lower().rstrip('.')}.",
            "image_query": f"{topic} close up detail",
            "type": "finding",
        })

    scenes.append({
        "text": f"These results could transform approaches to {topic}.",
        "image_query": "innovation future science",
        "type": "impact",
    })
    scenes.append({
        "text": f"Follow for more breakthroughs in {topic}.",
        "image_query": "science aesthetic minimal dark",
        "type": "cta",
    })

    return scenes


def _depersonalize(text: str) -> str:
    """Replace first-person language from abstracts with third-person."""
    replacements = [
        ("We show ", "The study shows "),
        ("We found ", "The team found "),
        ("We demonstrate ", "The study demonstrates "),
        ("We report ", "The authors report "),
        ("We identified ", "The team identified "),
        ("We discovered ", "The team discovered "),
        ("We observed ", "The team observed "),
        ("We propose ", "The authors propose "),
        ("We developed ", "The team developed "),
        ("We present ", "The study presents "),
        ("we show ", "the study shows "),
        ("we found ", "the team found "),
        ("we demonstrate ", "the study demonstrates "),
        ("Our findings ", "The findings "),
        ("Our results ", "The results "),
        ("Our data ", "The data "),
        ("our findings ", "the findings "),
        ("our results ", "the results "),
        ("our data ", "the data "),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


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
