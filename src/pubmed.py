"""Fetch recent PubMed articles with full metadata and optional PMC figures."""
import os
from datetime import datetime, timedelta
import requests


def gather_all(days_back: int = 3) -> list[dict]:
    """Fetch recent articles from PubMed with rich metadata."""
    email = os.environ.get("PUBMED_EMAIL", "revue@example.com")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")

    query = (
        '("Nature"[Journal] OR "Science"[Journal] OR "Cell"[Journal] '
        'OR "Lancet"[Journal] OR "N Engl J Med"[Journal]) '
        f'AND ("{date_from}"[PDAT] : "{date_to}"[PDAT])'
    )

    try:
        resp = requests.get(f"{base}/esearch.fcgi", params={
            "db": "pubmed", "term": query, "retmax": 20,
            "retmode": "json", "email": email,
        }, timeout=15)
        resp.raise_for_status()
        ids = resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        resp2 = requests.get(f"{base}/esummary.fcgi", params={
            "db": "pubmed", "id": ",".join(ids[:10]),
            "retmode": "json", "email": email,
        }, timeout=15)
        resp2.raise_for_status()
        result = resp2.json().get("result", {})

        articles = []
        for pmid in ids[:10]:
            info = result.get(pmid, {})
            authors = info.get("authors", [])
            author_str = authors[0].get("name", "") if authors else ""
            if len(authors) > 1:
                author_str += f" et al."

            articles.append({
                "pmid": pmid,
                "title": info.get("title", f"Article {pmid}"),
                "authors": author_str,
                "journal": info.get("source", ""),
                "date": info.get("pubdate", ""),
                "topic": _extract_topic(info.get("source", "")),
                "figure_urls": [],
            })

        # Try to get PMC figures for top articles
        for art in articles[:3]:
            art["figure_urls"] = _fetch_pmc_figures(art["pmid"], email)

        return articles
    except Exception as e:
        print(f"PubMed error: {e}")
        return []


def _fetch_pmc_figures(pmid: str, email: str) -> list[str]:
    """Try to fetch figure URLs from PMC open access."""
    try:
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": pmid, "format": "json", "email": email},
            timeout=10,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if not records or "pmcid" not in records[0]:
            return []

        pmcid = records[0]["pmcid"]
        oa_resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
            params={"id": pmcid, "format": "json"},
            timeout=10,
        )
        if oa_resp.status_code != 200:
            return []

        # Try to get figure images from PMC
        fig_resp = requests.get(
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
            headers={"Accept": "text/html"},
            timeout=10,
        )
        if fig_resp.status_code != 200:
            return []

        # Extract figure image URLs from HTML
        import re
        fig_urls = re.findall(
            r'https://www\.ncbi\.nlm\.nih\.gov/pmc/articles/PMC\d+/bin/[^"]+\.jpg',
            fig_resp.text
        )
        return fig_urls[:3]
    except Exception:
        return []


def _extract_topic(source: str) -> str:
    source_lower = source.lower()
    for journal, topic in [
        ("nature", "biology research"),
        ("science", "scientific discovery"),
        ("cell", "cell biology molecular"),
        ("lancet", "medicine health"),
        ("n engl j med", "clinical medicine"),
    ]:
        if journal in source_lower:
            return topic
    return "science"
