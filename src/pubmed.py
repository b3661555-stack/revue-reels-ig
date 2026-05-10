"""Fetch PubMed articles with abstract, metadata, and PMC figure URLs."""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET
import requests


def gather_all(days_back: int = 3) -> list[dict]:
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
        # Search
        resp = requests.get(f"{base}/esearch.fcgi", params={
            "db": "pubmed", "term": query, "retmax": 20,
            "retmode": "json", "email": email,
        }, timeout=15)
        resp.raise_for_status()
        ids = resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Summary (title, journal, authors, date)
        resp2 = requests.get(f"{base}/esummary.fcgi", params={
            "db": "pubmed", "id": ",".join(ids[:10]),
            "retmode": "json", "email": email,
        }, timeout=15)
        resp2.raise_for_status()
        summary = resp2.json().get("result", {})

        # Abstracts (XML)
        resp3 = requests.get(f"{base}/efetch.fcgi", params={
            "db": "pubmed", "id": ",".join(ids[:10]),
            "rettype": "abstract", "retmode": "xml", "email": email,
        }, timeout=20)
        abstracts = _parse_abstracts(resp3.text) if resp3.status_code == 200 else {}
        dois = _parse_dois(resp3.text) if resp3.status_code == 200 else {}

        articles = []
        for pmid in ids[:10]:
            info = summary.get(pmid, {})
            authors = info.get("authors", [])
            author_names = [a.get("name", "") for a in authors[:3]]
            author_str = ", ".join(author_names)
            if len(authors) > 3:
                author_str += " et al."

            articles.append({
                "pmid": pmid,
                "title": info.get("title", f"Article {pmid}"),
                "authors": author_str,
                "journal": info.get("source", ""),
                "date": info.get("pubdate", ""),
                "abstract": abstracts.get(pmid, ""),
                "topic": _extract_topic(info.get("source", "")),
                "doi": dois.get(pmid, ""),
                "figure_urls": [],
            })

        # Fetch PMC figures + PMCID for top articles
        for art in articles[:5]:
            pmcid, figs = _fetch_pmc_figures_and_id(art["pmid"], email)
            art["figure_urls"] = figs
            art["pmcid"] = pmcid
            if not figs and art.get("doi"):
                art["figure_urls"] = fetch_figures_from_doi(art["doi"])

        return articles
    except Exception as e:
        print(f"PubMed error: {e}")
        return []


def _parse_abstracts(xml_text: str) -> dict[str, str]:
    """Parse efetch XML to extract abstracts keyed by PMID."""
    result = {}
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            pmid = pmid_el.text

            abstract_parts = []
            for text_el in article.findall(".//AbstractText"):
                label = text_el.get("Label", "")
                text = "".join(text_el.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            result[pmid] = " ".join(abstract_parts)
    except Exception:
        pass
    return result


def _fetch_pmc_figures_and_id(pmid: str, email: str) -> tuple[str, list[str]]:
    """Fetch PMCID and figure image URLs from PMC if article is open access."""
    try:
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": pmid, "format": "json", "email": email},
            timeout=10,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if not records or "pmcid" not in records[0]:
            return "", []

        pmcid = records[0]["pmcid"]

        resp2 = requests.get(
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
            headers={"User-Agent": f"RevueReelsBot/1.0 (mailto:{email})"},
            timeout=15,
        )
        if resp2.status_code != 200:
            return pmcid, []

        urls = []
        urls += re.findall(
            rf'https://www\.ncbi\.nlm\.nih\.gov/pmc/articles/{pmcid}/bin/[^"\']+\.(?:jpg|png|gif)',
            resp2.text
        )
        urls += re.findall(
            rf'https://[^"\']*?/pmc/articles/{pmcid}/figure/[^"\']+',
            resp2.text
        )
        urls += re.findall(
            r'https://cdn\.ncbi\.nlm\.nih\.gov/pmc/articleimages/[^"\']+\.(?:jpg|png)',
            resp2.text
        )

        seen = set()
        unique = []
        for u in urls:
            key = u.split("/")[-1].split("?")[0]
            if key not in seen:
                seen.add(key)
                unique.append(u)

        if unique:
            print(f"  PMC figures for {pmcid}: {len(unique)} found")
        return pmcid, unique[:5]
    except Exception:
        return "", []


def fetch_pdf(pmcid: str, output_path: Path, email: str = "") -> bool:
    """Download PDF from PMC for open-access articles."""
    if not pmcid:
        return False
    try:
        resp = requests.get(
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/",
            headers={"User-Agent": f"RevueReelsBot/1.0 (mailto:{email})"},
            timeout=30,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return False
        ct = resp.headers.get("Content-Type", "")
        if "pdf" not in ct and not resp.content[:5] == b"%PDF-":
            return False
        output_path.write_bytes(resp.content)
        print(f"  PDF downloaded: {len(resp.content) // 1024}KB")
        return True
    except Exception as e:
        print(f"  PDF fetch failed: {e}")
        return False


def screenshot_article_page(pmid: str, doi: str, output_path: Path) -> bool:
    """Screenshot PubMed abstract page using Playwright."""
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 1600})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        if output_path.exists() and output_path.stat().st_size > 50000:
            print(f"  PubMed screenshot: {output_path.stat().st_size // 1024}KB")
            return True
        print(f"  PubMed screenshot too small: {output_path.stat().st_size // 1024}KB")
        return False
    except Exception as e:
        print(f"  Playwright screenshot failed: {e}")
        return False


def fetch_pdf_via_unpaywall(doi: str, output_path: Path, email: str = "") -> bool:
    """Fetch open-access PDF via Unpaywall API."""
    if not doi:
        return False
    try:
        api_email = email or os.environ.get("PUBMED_EMAIL", "revuereels@proton.me")
        resp = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": api_email},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  Unpaywall: HTTP {resp.status_code}")
            return False
        data = resp.json()
        pdf_url = None
        boa = data.get("best_oa_location") or {}
        pdf_url = boa.get("url_for_pdf") or boa.get("url")
        if not pdf_url:
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        if not pdf_url:
            print(f"  Unpaywall: no OA PDF for {doi}")
            return False
        pdf_resp = requests.get(
            pdf_url, timeout=30, allow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        )
        if pdf_resp.status_code != 200:
            print(f"  Unpaywall PDF: HTTP {pdf_resp.status_code}")
            return False
        if b"%PDF" not in pdf_resp.content[:10] and "pdf" not in pdf_resp.headers.get("Content-Type", ""):
            print(f"  Unpaywall: not a PDF")
            return False
        output_path.write_bytes(pdf_resp.content)
        print(f"  Unpaywall PDF: {len(pdf_resp.content) // 1024}KB")
        return True
    except Exception as e:
        print(f"  Unpaywall failed: {e}")
        return False


def _parse_dois(xml_text: str) -> dict[str, str]:
    """Parse DOIs from efetch XML keyed by PMID."""
    result = {}
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            pmid = pmid_el.text
            for aid in article.findall(".//ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    result[pmid] = aid.text
                    break
            if pmid not in result:
                for eloc in article.findall(".//ELocationID"):
                    if eloc.get("EIdType") == "doi" and eloc.text:
                        result[pmid] = eloc.text
                        break
    except Exception:
        pass
    return result


_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_article_preview(doi: str, output_path: Path) -> bool:
    """Fetch article preview image via DOI landing page og:image."""
    if not doi:
        return False
    try:
        resp = requests.get(
            f"https://doi.org/{doi}",
            timeout=20,
            allow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        )
        if resp.status_code != 200:
            print(f"  Article preview: HTTP {resp.status_code} for {doi}")
            return False
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                resp.text,
            )
        if not match:
            print(f"  Article preview: no og:image found for {doi}")
            return False
        img_url = match.group(1)
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        img_resp = requests.get(img_url, timeout=15, headers={
            "User-Agent": _BROWSER_UA,
        })
        if img_resp.status_code != 200 or len(img_resp.content) < 5000:
            print(f"  Article preview: image fetch failed ({img_resp.status_code})")
            return False
        output_path.write_bytes(img_resp.content)
        print(f"  Article preview: {len(img_resp.content) // 1024}KB ({doi})")
        return True
    except Exception as e:
        print(f"  Article preview failed: {e}")
        return False


def fetch_figures_from_doi(doi: str) -> list[str]:
    """Scrape figure thumbnail URLs from DOI landing page."""
    if not doi:
        return []
    try:
        resp = requests.get(
            f"https://doi.org/{doi}",
            timeout=20,
            allow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        )
        if resp.status_code != 200:
            return []
        urls = []
        urls += re.findall(
            r'https://media\.springernature\.com/[^"\'>\s]+\.(?:jpg|png|gif)',
            resp.text,
        )
        urls += re.findall(
            r'https://[^"\'>\s]*science\.org[^"\'>\s]+/F\d+\.[^"\'>\s]+\.jpg',
            resp.text,
        )
        urls += re.findall(
            r'https://[^"\'>\s]*els-cdn\.com[^"\'>\s]+\.(?:jpg|png)',
            resp.text,
        )
        urls += re.findall(
            r'https://cdn\.ncbi\.nlm\.nih\.gov/pmc/articleimages/[^"\'>\s]+\.(?:jpg|png)',
            resp.text,
        )
        seen = set()
        unique = []
        for u in urls:
            if any(x in u.lower() for x in ["logo", "icon", "banner", "avatar", "badge", "1x1"]):
                continue
            key = u.split("/")[-1].split("?")[0]
            if key not in seen:
                seen.add(key)
                unique.append(u)
        if unique:
            print(f"  DOI figures for {doi}: {len(unique)} found")
        return unique[:8]
    except Exception:
        return []


def _extract_topic(source: str) -> str:
    s = source.lower()
    for journal, topic in [
        ("nature", "biology research"),
        ("science", "scientific discovery"),
        ("cell", "cell biology molecular"),
        ("lancet", "medicine health"),
        ("n engl j med", "clinical medicine"),
    ]:
        if journal in s:
            return topic
    return "science"
