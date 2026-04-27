import os
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")

def search_web(query: str) -> str:
    if not query or not query.strip():
        return "Search error: empty query."

    # First choice: local SearxNG instance.
    searx_result = _search_searxng(query.strip())
    if searx_result is not None:
        return searx_result

    # Fallback: parse DuckDuckGo HTML results when SearxNG is unavailable.
    ddg_result = _search_duckduckgo(query.strip())
    if ddg_result is not None:
        return ddg_result

    return "Search error: no search backend returned results."


def _search_searxng(query: str) -> str | None:
    try:
        params = {
            "q": query,
            "format": "json",
            "engines": "google,bing",
            "categories": "general",
        }
        resp = requests.get(
            f"{SEARXNG_URL}/search",
            params=params,
            headers={"Accept": "application/json"},
            timeout=12,
        )
        resp.raise_for_status()

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            return None

        payload = resp.json()
        results = payload.get("results") or []
        formatted = []
        for r in results[:5]:
            title = (r.get("title") or "Untitled").strip()
            snippet = (r.get("content") or "").strip().replace("\n", " ")[:220]
            url = (r.get("url") or "").strip()
            if url:
                formatted.append(f"{title}: {snippet} ({url})")

        return "\n".join(formatted) if formatted else "No results found."
    except Exception:
        return None


def _search_duckduckgo(query: str) -> str | None:
    try:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(".result")
        formatted = []

        for row in rows[:5]:
            title_el = row.select_one(".result__a")
            snippet_el = row.select_one(".result__snippet")
            if not title_el:
                continue

            title = title_el.get_text(" ", strip=True)
            href = title_el.get("href", "").strip()
            snippet = snippet_el.get_text(" ", strip=True)[:220] if snippet_el else ""

            if href:
                formatted.append(f"{title}: {snippet} ({href})")

        return "\n".join(formatted) if formatted else "No results found."
    except Exception:
        return None