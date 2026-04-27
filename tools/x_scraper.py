import requests
from bs4 import BeautifulSoup

def scrape_x_post(url: str) -> str:
    """Try yt-dlp first, fall back to Nitter scrape"""
    # Method 1: yt-dlp (best for X/Twitter)
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "skip_download": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title") or info.get("description") or ""
            uploader = info.get("uploader") or info.get("channel") or ""
            text = info.get("description") or title
            return f"@{uploader}: {text}" if text else "Could not extract post via yt-dlp."
    except Exception as e:
        print(f"yt-dlp failed: {e}, trying Nitter...")

    # Method 2: Nitter fallback
    try:
        nitter_url = url.replace("twitter.com", "nitter.net").replace("x.com", "nitter.net")
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(nitter_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        tweet = soup.find("div", class_="tweet-content")
        if tweet:
            return tweet.get_text(strip=True)
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text() for p in paragraphs[:5])
        return text or "Could not extract post."
    except Exception as e:
        return f"Scrape error: {e}"