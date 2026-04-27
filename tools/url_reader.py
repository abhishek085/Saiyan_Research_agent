import requests
from bs4 import BeautifulSoup
import re

def read_url(url: str) -> str:
    """Smart URL reader — handles GitHub, PDFs, articles, YouTube, etc."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        # GitHub repo special handling
        if "github.com" in url:
            return _github_reader(resp.text, url)
        
        # PDF — can't read, just return metadata
        if url.lower().endswith(".pdf"):
            return f"PDF file detected: {url}\nCannot extract text directly. Download manually."
        
        # YouTube — extract title + description
        if "youtube.com" in url or "youtu.be" in url:
            return _youtube_reader(url)
        
        # General article
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        
        # Article/main content
        main = soup.find("article") or soup.find("main") or soup.find("body") or soup.find("div", class_=re.compile(r"content|article"))
        if not main:
            return _fallback_for_js_heavy_pages(url, resp.text)
        
        text = main.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 20]
        content = "\n".join(lines[:50])  # first 50 meaningful lines
        if content and len(content) >= 250:
            return content[:8000]

        return _fallback_for_js_heavy_pages(url, resp.text)
    
    except Exception as e:
        return f"URL read error: {e}"


def _fallback_for_js_heavy_pages(url: str, html: str) -> str:
    # Try extracting embedded JSON with text fields first.
    soup = BeautifulSoup(html, "html.parser")
    extracted_lines = []

    for script in soup.find_all("script"):
        text = script.get_text("\n", strip=True)
        if not text:
            continue
        if "blog" not in text.lower() and "article" not in text.lower():
            continue

        candidates = re.findall(r'"(?:title|summary|content|description|text)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
        for c in candidates:
            cleaned = (
                c.replace("\\n", " ")
                .replace("\\/", "/")
                .replace("\\\"", '"')
                .strip()
            )
            if len(cleaned) > 30:
                extracted_lines.append(cleaned)

    if extracted_lines:
        deduped = []
        seen = set()
        for line in extracted_lines:
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(line)
            if len(deduped) >= 40:
                break
        return "\n".join(deduped)[:8000]

    # Final fallback for JS-rendered pages: ask a plain-text mirror to fetch readable content.
    try:
        proxy_url = "https://r.jina.ai/http://" + url.replace("https://", "").replace("http://", "")
        proxy_resp = requests.get(proxy_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        proxy_resp.raise_for_status()
        proxy_text = proxy_resp.text.strip()
        if proxy_text and len(proxy_text) > 200:
            lines = [l.strip() for l in proxy_text.splitlines() if l.strip()]
            return "\n".join(lines[:120])[:8000]
    except Exception:
        pass

    return "Page appears empty or JavaScript-heavy."

def _github_reader(html: str, url: str) -> str:
    """Special GitHub repo reader — extracts README, description, stats"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Repo title
    title = soup.find("h1", class_="octicon-title") or soup.find("h1")
    repo_title = title.get_text(strip=True) if title else "Unknown repo"
    
    # Repo description
    desc = soup.find("p", class_="repo-description") or soup.find("meta", attrs={"name": "description"})
    description = desc.get("content", desc.get_text(strip=True)) if desc else "No description"
    
    # README content
    readme = soup.find("div", class_="markdown-body") or soup.find("article", class_="readme")
    readme_text = ""
    if readme:
        # Extract main sections
        h2s = readme.find_all("h2")
        sections = []
        for h2 in h2s[:5]:  # first 5 sections
            section_title = h2.get_text(strip=True)
            next_p = h2.find_next_sibling("p")
            if next_p:
                section_text = next_p.get_text(strip=True)
                sections.append(f"{section_title}:\n{section_text}")
        readme_text = "\n\n".join(sections) 
    return f"Repository: {repo_title}\nDescription: {description}\nREADME:\n{readme_text}"


def _youtube_reader(url: str) -> str:
    """Extract basic metadata for YouTube pages without full transcript parsing."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title = ""
        description = ""

        title_meta = soup.find("meta", attrs={"property": "og:title"})
        if title_meta and title_meta.get("content"):
            title = title_meta.get("content").strip()

        desc_meta = soup.find("meta", attrs={"property": "og:description"})
        if desc_meta and desc_meta.get("content"):
            description = desc_meta.get("content").strip()

        parts = ["YouTube URL read:"]
        if title:
            parts.append(f"Title: {title}")
        if description:
            parts.append(f"Description: {description[:2000]}")
        if not title and not description:
            parts.append("Could not extract title/description from this YouTube page.")

        return "\n".join(parts)
    except Exception as e:
        return f"YouTube read error: {e}"