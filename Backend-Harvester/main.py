import json
import time
import requests
import feedparser
import socket
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ==========================================
# Little Mere News - Harvester Script
# ==========================================

# Global timeout to prevent infinite hangs from Cloudflare/slow websites
socket.setdefaulttimeout(15)

# ==========================================
# Little Mere News - Harvester Script
# ==========================================

# Configurations
OLLAMA_API_URL = "http://10.0.100.20:11434/api/generate"
FEEDS_FILE = "/home/lmnadmin/feeds.json"
OUTPUT_FILE = "/home/lmnadmin/news_to_publish.json"
HOURS_LIMIT = 24
MAX_PER_FEED = 2 # Prevent overloading the local AI

def clean_html(raw_html):
    """Remove HTML tags and return clean text."""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def parse_date(entry):
    """Extract publication date from RSS entry."""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime.fromtimestamp(time.mktime(entry.published_parsed))
    return datetime.now()

def call_ollama(text):
    """Call the local Llama 3 model for translation and summarization."""
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
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300) # 5 min timeout for heavy processing
        response.raise_for_status()
        result = response.json()
        return json.loads(result["response"])
    except Exception as e:
        print(f"[ERROR] Failed to process via Ollama: {e}")
        return None

def main():
    print("[1/3] Loading feeds configuration...")
    try:
        with open(FEEDS_FILE, 'r', encoding='utf-8') as f:
            categories = json.load(f)
    except FileNotFoundError:
        print(f"[FATAL] {FEEDS_FILE} not found.")
        return

    cutoff_date = datetime.now() - timedelta(hours=HOURS_LIMIT)
    processed_news = []

    print("[2/3] Starting RSS Harvesting and AI Processing...")
    for category, feeds in categories.items():
        for feed_url in feeds:
            print(f"  -> Polling: {feed_url} [{category}]")
            
            try:
                feed = feedparser.parse(feed_url)
            except Exception as e:
                print(f"     [ERROR] Failed to fetch feed {feed_url}: {e}")
                continue
                
            count = 0
            
            for entry in feed.entries:
                if count >= MAX_PER_FEED:
                    break
                    
                pub_date = parse_date(entry)
                if pub_date < cutoff_date:
                    continue
                
                print(f"     + Processing: {entry.title}")
                content = entry.summary if hasattr(entry, 'summary') else entry.title
                clean_content = clean_html(content)[:2500] # Cap at 2500 chars to avoid memory exhaustion
                
                ai_result = call_ollama(clean_content)
                if ai_result:
                    article_data = {
                        "category": category,
                        "source_name": feed.feed.title if hasattr(feed.feed, 'title') else "Unknown Source",
                        "source_url": entry.link,
                        "title_en": ai_result.get("title_en", entry.title),
                        "title_pt": ai_result.get("title_pt", ""),
                        "summary_en": ai_result.get("summary_en", ""),
                        "summary_pt": ai_result.get("summary_pt", "")
                    }
                    processed_news.append(article_data)
                    count += 1
                
                time.sleep(2) # Give the GPU/RAM a brief cooldown

    print(f"[3/3] Harvesting complete. Saving {len(processed_news)} articles...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_news, f, indent=4, ensure_ascii=False)
        
    print("Done!")

if __name__ == "__main__":
    main()
