import json
import socket
import time
from datetime import datetime, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

# ==========================================
# Little Mere News - Harvester Script
# ==========================================

# Global timeout to prevent infinite hangs from slow websites.
socket.setdefaulttimeout(15)

OLLAMA_API_URL = "http://10.0.100.20:11434/api/generate"
FEEDS_FILE = "/home/lmnadmin/feeds.json"
OUTPUT_FILE = "/home/lmnadmin/news_to_publish.json"
HOURS_LIMIT = 24
MAX_PER_FEED = 2  # Prevent overloading the local AI

AI_REQUIRED_FIELDS = ("title_en", "title_pt", "summary_en", "summary_pt")


def clean_html(raw_html):
    """Remove HTML tags and return normalized visible text."""
    if not isinstance(raw_html, str):
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_date(entry, now=None):
    """Extract a publication date from an RSS entry.

    Missing or malformed dates deliberately fall back to ``now`` so callers can
    decide how to treat undated feed items without crashing the whole feed.
    """
    fallback = now or datetime.now()
    published = getattr(entry, "published_parsed", None)
    if not published:
        return fallback

    try:
        return datetime.fromtimestamp(time.mktime(published))
    except (OverflowError, TypeError, ValueError):
        return fallback


def validate_ai_result(value):
    """Validate the deterministic contract expected from the AI provider.

    The publisher must never receive arbitrary/malformed model output. Every
    required field must be a non-empty string. Extra keys are ignored by the
    article construction step.
    """
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


def call_ollama(text):
    """Call the local model and return only schema-valid structured output."""
    prompt = f"""
You are a highly professional technology journalist and SEO expert.
Read the following news article excerpt.

Create a highly engaging, original, SEO-friendly summary in English (about 2 paragraphs).
Then, provide a high-quality, localized translation of that summary into Brazilian Portuguese.
The tone in both languages must be similar, professional, and journalistic.

CRITICAL RULES:
- NEVER use emojis anywhere in your response. Not a single one.
- Output ONLY valid JSON. Do not use markdown blocks like ```json.
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
        "model": "llama3:latest",
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        response.raise_for_status()
        result = decode_ollama_response(response.json())
        if result is None:
            print("[ERROR] Ollama returned malformed or schema-invalid output.")
        return result
    except (requests.RequestException, ValueError) as exc:
        print(f"[ERROR] Failed to process via Ollama: {exc}")
        return None


def main():
    print("[1/3] Loading feeds configuration...")
    try:
        with open(FEEDS_FILE, "r", encoding="utf-8") as file_handle:
            categories = json.load(file_handle)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[FATAL] Could not load {FEEDS_FILE}: {exc}")
        return

    cutoff_date = datetime.now() - timedelta(hours=HOURS_LIMIT)
    processed_news = []

    print("[2/3] Starting RSS Harvesting and AI Processing...")
    for category, feeds in categories.items():
        for feed_url in feeds:
            print(f"  -> Polling: {feed_url} [{category}]")

            try:
                feed = feedparser.parse(feed_url)
            except Exception as exc:
                # feedparser integrations are isolated per source: one broken source
                # must not abort the remaining pipeline.
                print(f"     [ERROR] Failed to fetch feed {feed_url}: {exc}")
                continue

            count = 0
            for entry in feed.entries:
                if count >= MAX_PER_FEED:
                    break

                pub_date = parse_date(entry)
                if pub_date < cutoff_date:
                    continue

                entry_title = getattr(entry, "title", "Untitled")
                print(f"     + Processing: {entry_title}")
                content = getattr(entry, "summary", entry_title)
                clean_content = clean_html(content)[:2500]
                if not clean_content:
                    print("     [SKIP] Empty article content after normalization.")
                    continue

                ai_result = call_ollama(clean_content)
                if ai_result:
                    article_data = {
                        "category": category,
                        "source_name": getattr(feed.feed, "title", "Unknown Source"),
                        "source_url": getattr(entry, "link", ""),
                        **ai_result,
                    }
                    processed_news.append(article_data)
                    count += 1

                time.sleep(2)

    print(f"[3/3] Harvesting complete. Saving {len(processed_news)} articles...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_handle:
        json.dump(processed_news, file_handle, indent=4, ensure_ascii=False)

    print("Done!")


if __name__ == "__main__":
    main()
