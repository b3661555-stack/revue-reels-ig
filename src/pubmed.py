"""Fetch recent PubMed articles for reel content."""
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
import requests


def gather_all(days_back: int = 3) -> list[dict]:
    """Fetch recent articles from PubMed E-utilities."""
    email = os.environ.get("PUBMED_EMAIL", "revue@example.com")
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")

    query = (
        "(Nature OR Science OR Cell OR Lancet OR \"NEJM\") "
        f"AND (\"{date_from}\"[PDAT] : \"{date_to}\"[PDAT])"
    )

    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 50,
        "rettype": "json",
        "email": email,
    }

    try:
        resp = requests.get(f"{base_url}/esearch.fcgi", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        ids = data.get("esearchresult", {}).get("idlist", [])
        for pmid in ids[:5]:  # Limit to 5 for reel
            articles.append({
                "pmid": pmid,
                "title": f"Article {pmid}",
                "topic": "science",
            })
        return articles
    except Exception as e:
        print(f"PubMed error: {e}")
        return []
