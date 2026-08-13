import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from supabase import Client, create_client

# ==========================================
# Little Mere News - Publisher Script
# ==========================================

DEFAULT_INPUT_FILE = Path("/home/lmnadmin/news_to_publish.json")
DEFAULT_REJECTED_FILE = Path("/home/lmnadmin/news_to_publish.rejected.json")
REQUIRED_FIELDS = (
    "category",
    "source_name",
    "source_url",
    "title_en",
    "title_pt",
    "summary_en",
    "summary_pt",
)
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0


def get_queue_paths(environ=None):
    """Resolve queue paths from environment while preserving legacy defaults."""
    environ = os.environ if environ is None else environ
    input_file = Path(environ.get("LMN_INPUT_FILE", str(DEFAULT_INPUT_FILE))).expanduser()
    rejected_file = Path(environ.get("LMN_REJECTED_FILE", str(DEFAULT_REJECTED_FILE))).expanduser()

    if input_file.resolve(strict=False) == rejected_file.resolve(strict=False):
        raise ValueError("LMN_INPUT_FILE and LMN_REJECTED_FILE must be different paths")

    return input_file, rejected_file


def validate_item(item):
    """Return a normalized publisher item or None when the payload is invalid."""
    if not isinstance(item, dict):
        return None

    normalized = {}
    for field in REQUIRED_FIELDS:
        value = item.get(field)
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value:
            return None
        normalized[field] = value

    parsed_url = urlparse(normalized["source_url"])
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None

    return normalized


def atomic_write_json(path, payload):
    """Persist JSON atomically so an interrupted write cannot destroy the queue."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, ensure_ascii=False)
        file_handle.flush()
        os.fsync(file_handle.fileno())
    os.replace(temp_path, path)


def publish_item(client, item):
    """Publish one validated item idempotently by source_url.

    The database must enforce a UNIQUE constraint on news.source_url. Supabase's
    upsert with ignore_duplicates turns a conflict into a deterministic no-op,
    avoiding duplicate detection through free-form exception messages.
    """
    response = (
        client.table("news")
        .upsert(item, on_conflict="source_url", ignore_duplicates=True)
        .execute()
    )
    data = getattr(response, "data", None)
    return "published" if data else "duplicate"


def publish_with_retry(client, item, sleep_fn=time.sleep):
    """Retry only transient transport failures with a bounded attempt count."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return publish_item(client, item)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == MAX_ATTEMPTS:
                return "retryable_failure", exc
            sleep_fn(RETRY_BACKOFF_SECONDS * attempt)
        except Exception as exc:
            return "permanent_failure", exc

    raise AssertionError("unreachable")


def process_batch(client, news_items, sleep_fn=time.sleep):
    """Process a batch without losing retryable or permanently failed items."""
    retry_queue = []
    rejected = []
    counts = {
        "published": 0,
        "duplicate": 0,
        "retryable_failure": 0,
        "permanent_failure": 0,
        "invalid": 0,
    }

    for raw_item in news_items:
        item = validate_item(raw_item)
        if item is None:
            counts["invalid"] += 1
            rejected.append(raw_item)
            print("  [REJECT] Invalid publisher payload.")
            continue

        result = publish_with_retry(client, item, sleep_fn=sleep_fn)
        if isinstance(result, tuple):
            status, exc = result
            counts[status] += 1
            retry_queue.append(item)
            print(f"  [ERROR] {status} for {item['source_url']}: {type(exc).__name__}")
            continue

        counts[result] += 1
        if result == "published":
            print(f"  [+] Published: {item['title_en']}")
        else:
            print(f"  [SKIP] Already published: {item['source_url']}")

    return counts, retry_queue, rejected


def main():
    print("[1/3] Initializing Publisher...")

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("[FATAL] SUPABASE_URL and SUPABASE_KEY must be set in the environment.")
        return 1

    try:
        input_file, rejected_file = get_queue_paths()
    except ValueError as exc:
        print(f"[FATAL] Invalid publisher queue configuration: {exc}")
        return 1

    if not input_file.exists():
        print(f"[INFO] File {input_file} not found. Nothing to publish.")
        return 0

    print("[2/3] Reading processed news payload...")
    try:
        with input_file.open("r", encoding="utf-8") as file_handle:
            news_items = json.load(file_handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FATAL] Could not read publisher queue: {type(exc).__name__}")
        return 1

    if not isinstance(news_items, list):
        print("[FATAL] Publisher queue must be a JSON array.")
        return 1

    if not news_items:
        input_file.unlink(missing_ok=True)
        print("[INFO] No news items to publish.")
        return 0

    client: Client = create_client(supabase_url, supabase_key)
    print(f"[3/3] Uploading {len(news_items)} items to Supabase...")
    counts, retry_queue, rejected = process_batch(client, news_items)

    if retry_queue:
        atomic_write_json(input_file, retry_queue)
    else:
        input_file.unlink(missing_ok=True)

    if rejected:
        existing_rejected = []
        if rejected_file.exists():
            try:
                with rejected_file.open("r", encoding="utf-8") as file_handle:
                    loaded = json.load(file_handle)
                    if isinstance(loaded, list):
                        existing_rejected = loaded
            except (OSError, json.JSONDecodeError):
                pass
        atomic_write_json(rejected_file, [*existing_rejected, *rejected])

    print("=========================================")
    print(
        " Publish complete: "
        f"{counts['published']} new, {counts['duplicate']} duplicate, "
        f"{len(retry_queue)} queued for retry, {len(rejected)} rejected."
    )
    print("=========================================")

    return 1 if retry_queue else 0


if __name__ == "__main__":
    raise SystemExit(main())
