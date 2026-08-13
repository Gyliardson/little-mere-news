import calendar
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# ==========================================
# Little Mere News - Harvester Script
# ==========================================

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://10.0.100.20:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
FEEDS_FILE = os.getenv("LMN_FEEDS_FILE", "/home/lmnadmin/feeds.json")
OUTPUT_FILE = os.getenv("LMN_OUTPUT_FILE", "/home/lmnadmin/news_to_publish.json")
HOURS_LIMIT = 24
MAX_PER_FEED = 2
SOURCE_TIMEOUT_SECONDS = 15
AI_TIMEOUT_SECONDS = 60
MAX_RETRIES = 2
AI_REQUIRED_FIELDS = ("title_en", "title_pt", "summary_en", "summary_pt")


def clean_html(raw_html):
    """Remove HTML tags and return normalized visible text."""
    if not isinstance(raw_html, str):
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_date(entry):
    """Return an aware UTC publication datetime, or None when unavailable/invalid."""
    published = getattr(entry, "published_parsed", None)
    if not published:
        return None
    try:
        timestamp = calendar.timegm(published)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, TypeError, ValueError):
        return None


def valid_source_url(value):
    """Accept only absolute HTTP(S) URLs as durable article identity."""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_ai_result(value):
    """Validate the structured article contract expected from the AI provider."""
    if not isinstance(value, dict):
        return None
    normalized = {}
    for field in AI_REQUIRED_FIELDS:
        field_value = value.get(field)
        if not isinstance(field_value, str):
            return None
        field_value = field_value.strip()
        if not field_value:
            return None
        normalized[field] = field_value
    return normalized


def decode_ollama_response(payload):
    """Decode and validate an Ollama API response without performing I/O."""
    if not isinstance(payload, dict):
        return None
    response_text = payload.get("response")
    if not isinstance(response_text, str):
        return None
    try:
        decoded = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return None
    return validate_ai_result(decoded)


class OllamaProvider:
    """Small replaceable boundary around the local Ollama transport."""

    def __init__(self, url=OLLAMA_API_URL, model=OLLAMA_MODEL, session=requests):
        self.url = url
        self.model = model
        self.session = session

    def process(self, text):
        prompt = f"""
You are a highly professional technology journalist and SEO expert.
Read the following news article excerpt.

Create a highly engaging, original, SEO-friendly summary in English (about 2 paragraphs).
Then, provide a high-quality, localized translation of that summary into Brazilian Portuguese.
The tone in both languages must be similar, professional, and journalistic.

CRITICAL RULES:
- NEVER use emojis anywhere in your response. Not a single one.
- Output ONLY valid JSON. Do not use markdown blocks.
- The JSON structure MUST strictly follow this exact format:
{{
    "title_en": "SEO rewritten english title",
    "title_pt": "Translated portuguese title",
    "summary_en": "Your original English summary...",
    "summary_pt": "Your translated Portuguese summary..."
}}

Article Excerpt:
{text}
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.session.post(self.url, json=payload, timeout=AI_TIMEOUT_SECONDS)
                response.raise_for_status()
                return decode_ollama_response(response.json())
            except (requests.RequestException, ValueError) as exc:
                if attempt >= MAX_RETRIES:
                    print(f"[ERROR] AI provider unavailable after retries: {exc}")
                    return None
                time.sleep(0.5 * (attempt + 1))
        return None


def fetch_feed(feed_url, session=requests):
    """Fetch one feed with bounded transport behavior and parse it from bytes."""
    if not valid_source_url(feed_url):
        raise ValueError(f"Invalid feed URL: {feed_url!r}")
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(feed_url, timeout=SOURCE_TIMEOUT_SECONDS)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if getattr(parsed, "bozo", False):
                raise ValueError(f"Malformed feed: {getattr(parsed, 'bozo_exception', 'parse error')}")
            return parsed
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Feed unavailable after retries: {feed_url}: {last_error}")


def atomic_write_json(path, value):
    """Persist JSON using same-directory atomic replacement."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file_handle:
            json.dump(value, file_handle, indent=4, ensure_ascii=False)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()


def harvest(categories, provider=None, now=None, feed_loader=fetch_feed):
    """Run deterministic orchestration while isolating every external feed."""
    provider = provider or OllamaProvider()
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    cutoff_date = now_utc.astimezone(timezone.utc) - timedelta(hours=HOURS_LIMIT)
    processed_news = []

    for category, feeds in categories.items():
        for feed_url in feeds:
            print(f"  -> Polling: {feed_url} [{category}]")
            try:
                feed = feed_loader(feed_url)
            except Exception as exc:
                print(f"     [ERROR] Failed to fetch feed {feed_url}: {exc}")
                continue

            count = 0
            for entry in getattr(feed, "entries", []):
                if count >= MAX_PER_FEED:
                    break

                pub_date = parse_date(entry)
                if pub_date is None:
                    print("     [SKIP] Missing or invalid publication date.")
                    continue
                if pub_date < cutoff_date:
                    continue

                source_url = getattr(entry, "link", None)
                if not valid_source_url(source_url):
                    print("     [SKIP] Missing or invalid source URL.")
                    continue

                entry_title = getattr(entry, "title", "Untitled")
                content = getattr(entry, "summary", entry_title)
                clean_content = clean_html(content)[:2500]
                if not clean_content:
                    print("     [SKIP] Empty article content after normalization.")
                    continue

                ai_result = provider.process(clean_content)
                if ai_result:
                    processed_news.append(
                        {
                            "category": category,
                            "source_name": getattr(getattr(feed, "feed", None), "title", "Unknown Source"),
                            "source_url": source_url.strip(),
                            **ai_result,
                        }
                    )
                    count += 1

    return processed_news


def main():
    print("[1/3] Loading feeds configuration...")
    try:
        with open(FEEDS_FILE, "r", encoding="utf-8") as file_handle:
            categories = json.load(file_handle)
        if not isinstance(categories, dict):
            raise ValueError("feeds configuration must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[FATAL] Could not load {FEEDS_FILE}: {exc}")
        return

    print("[2/3] Starting RSS Harvesting and AI Processing...")
    processed_news = harvest(categories)

    print(f"[3/3] Harvesting complete. Saving {len(processed_news)} articles...")
    try:
        atomic_write_json(OUTPUT_FILE, processed_news)
    except OSError as exc:
        print(f"[FATAL] Could not persist queue atomically: {exc}")
        return
    print("Done!")


if __name__ == "__main__":
    main()
