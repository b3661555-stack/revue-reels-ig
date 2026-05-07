"""Fetch recent PubMed articles for reel content."""
import os
from datetime import datetime, timedelta
import requests


def gather_all(days_back: int = 3) -> list[dict]:
    """Fetch recent articles from PubMed E-utilities."""
    email = os.environ.get("PUBMED_EMAIL", "revue@example.com")
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")

    query = (
        '("Nature"[Journal] OR "Science"[Journal] OR "Cell"[Journal] '
        'OR "Lancet"[Journal] OR "N Engl J Med"[Journal]) '
        f'AND ("{date_from}"[PDAT] : "{date_to}"[PDAT])'
    )

    try:
        resp = requests.get(f"{base_url}/esearch.fcgi", params={
            "db": "pubmed",
            "term": query,
            "retmax": 20,
            "retmode": "json",
            "email": email,
        }, timeout=15)
        resp.raise_for_status()
        ids = resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Fetch titles via esummary
        resp2 = requests.get(f"{base_url}/esummary.fcgi", params={
            "db": "pubmed",
            "id": ",".join(ids[:10]),
            "retmode": "json",
            "email": email,
        }, timeout=15)
        resp2.raise_for_status()
        result = resp2.json().get("result", {})

        articles = []
        for pmid in ids[:10]:
            info = result.get(pmid, {})
            articles.append({
                "pmid": pmid,
                "title": info.get("title", f"Article {pmid}"),
                "topic": _extract_topic(info.get("source", "")),
            })
        return articles
    except Exception as e:
        print(f"PubMed error: {e}")
        return []


def _extract_topic(source: str) -> str:
    source_lower = source.lower()
    for journal, topic in [
        ("nature", "biology"),
        ("science", "science"),
        ("cell", "cell biology"),
        ("lancet", "medicine"),
        ("n engl j med", "medicine"),
    ]:
        if journal in source_lower:
            return topic
    return "science"
