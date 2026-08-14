import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from supabase import Client, create_client

from failure_policy import is_retryable_publish_exception

# ==========================================
# Little Mere News - Publisher Script
# ==========================================

DEFAULT_INPUT_FILE = Path("/home/lmnadmin/news_to_publish.inbound.json")
DEFAULT_RETRY_FILE = Path("/home/lmnadmin/news_to_publish.retry.json")
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


def _configured_file_path(environ, name, default):
    """Resolve one optional file path and reject empty/directory configuration."""
    raw_value = environ.get(name)
    if raw_value is None:
        path = Path(default)
    else:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{name} must not be empty")
        path = Path(value).expanduser()

    if path.exists() and path.is_dir():
        raise ValueError(f"{name} must point to a file, not a directory")

    return path


def get_queue_paths(environ=None):
    """Resolve distinct inbound, retry and rejected queue paths."""
    environ = os.environ if environ is None else environ
    input_file = _configured_file_path(environ, "LMN_INPUT_FILE", DEFAULT_INPUT_FILE)
    retry_file = _configured_file_path(environ, "LMN_RETRY_FILE", DEFAULT_RETRY_FILE)
    rejected_file = _configured_file_path(environ, "LMN_REJECTED_FILE", DEFAULT_REJECTED_FILE)

    resolved = {
        input_file.resolve(strict=False),
        retry_file.resolve(strict=False),
        rejected_file.resolve(strict=False),
    }
    if len(resolved) != 3:
        raise ValueError(
            "LMN_INPUT_FILE, LMN_RETRY_FILE and LMN_REJECTED_FILE must be different paths"
        )

    return input_file, retry_file, rejected_file


def get_queue_lock_path(input_file, retry_file, rejected_file):
    """Derive one lock file for the configured Publisher queue ownership set."""
    retry_file = Path(retry_file)
    lock_path = retry_file.with_name(f".{retry_file.name}.lock")
    resolved_lock = lock_path.resolve(strict=False)
    queue_paths = {
        Path(input_file).resolve(strict=False),
        retry_file.resolve(strict=False),
        Path(rejected_file).resolve(strict=False),
    }
    if resolved_lock in queue_paths:
        raise ValueError("Publisher queue lock path must be distinct from queue files")
    return lock_path


@contextmanager
def publisher_queue_lock(lock_path):
    """Fail closed when another process already owns this Publisher queue set."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another Publisher process already owns this queue set") from exc
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock_handle.close()


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


def load_queue(path):
    """Load a queue file and fail closed on malformed/non-array content."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, list):
        raise ValueError(f"Queue {path} must be a JSON array")
    return payload


def merge_queues(*queues):
    """Merge queues while collapsing valid duplicate source URLs deterministically."""
    merged = []
    seen_urls = set()
    for queue in queues:
        for item in queue:
            normalized = validate_item(item)
            if normalized is None:
                merged.append(item)
                continue
            source_url = normalized["source_url"]
            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)
            merged.append(item)
    return merged


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
    """Retry only explicitly classified transient failures with a bounded attempt count."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return publish_item(client, item)
        except Exception as exc:
            if not is_retryable_publish_exception(exc):
                return "permanent_failure", exc
            if attempt == MAX_ATTEMPTS:
                return "retryable_failure", exc
            sleep_fn(RETRY_BACKOFF_SECONDS * attempt)

    raise AssertionError("unreachable")


def process_batch(client, news_items, sleep_fn=time.sleep):
    """Process a batch, retaining transient failures and quarantining permanent ones."""
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
            if status == "retryable_failure":
                retry_queue.append(item)
                print(f"  [ERROR] retryable_failure for {item['source_url']}: {type(exc).__name__}")
            else:
                rejected.append(item)
                print(f"  [REJECT] permanent_failure for {item['source_url']}: {type(exc).__name__}")
            continue

        counts[result] += 1
        if result == "published":
            print(f"  [+] Published: {item['title_en']}")
        else:
            print(f"  [SKIP] Already published: {item['source_url']}")

    return counts, retry_queue, rejected


def append_rejected(rejected_file, rejected):
    """Append quarantined payloads durably without discarding previous quarantine data."""
    if not rejected:
        return
    existing_rejected = []
    if rejected_file.exists():
        existing_rejected = load_queue(rejected_file)
    atomic_write_json(rejected_file, [*existing_rejected, *rejected])


def run_locked_publisher(input_file, retry_file, rejected_file, supabase_url, supabase_key):
    """Execute the complete read/process/persist/unlink lifecycle under one queue owner."""
    if not input_file.exists() and not retry_file.exists():
        print("[INFO] No inbound or retry queue found. Nothing to publish.")
        return 0

    print("[2/3] Reading inbound and retained retry payloads...")
    try:
        retry_items = load_queue(retry_file)
        inbound_items = load_queue(input_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[FATAL] Could not read publisher queue: {type(exc).__name__}: {exc}")
        return 1

    news_items = merge_queues(retry_items, inbound_items)
    if not news_items:
        input_file.unlink(missing_ok=True)
        retry_file.unlink(missing_ok=True)
        print("[INFO] No news items to publish.")
        return 0

    client: Client = create_client(supabase_url, supabase_key)
    print(f"[3/3] Uploading {len(news_items)} items to Supabase...")
    counts, retry_queue, rejected = process_batch(client, news_items)

    try:
        if retry_queue:
            atomic_write_json(retry_file, retry_queue)
        else:
            retry_file.unlink(missing_ok=True)
        append_rejected(rejected_file, rejected)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[FATAL] Could not persist publisher result queues: {type(exc).__name__}: {exc}")
        return 1

    # The inbound file is relinquished only after all recoverable/quarantined result state is durable.
    input_file.unlink(missing_ok=True)

    print("=========================================")
    print(
        " Publish complete: "
        f"{counts['published']} new, {counts['duplicate']} duplicate, "
        f"{len(retry_queue)} retained for retry, {len(rejected)} rejected."
    )
    print("=========================================")

    # Signal newly produced retry/quarantine work once so orchestration does not report
    # a partially unsuccessful batch as green. Quarantined items are not reprocessed
    # on later no-work runs because they live outside inbound/retry ownership.
    return 1 if retry_queue or rejected else 0


def main():
    print("[1/3] Initializing Publisher...")

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("[FATAL] SUPABASE_URL and SUPABASE_KEY must be set in the environment.")
        return 1

    try:
        input_file, retry_file, rejected_file = get_queue_paths()
        lock_path = get_queue_lock_path(input_file, retry_file, rejected_file)
    except ValueError as exc:
        print(f"[FATAL] Invalid publisher queue configuration: {exc}")
        return 1

    try:
        with publisher_queue_lock(lock_path):
            return run_locked_publisher(
                input_file,
                retry_file,
                rejected_file,
                supabase_url,
                supabase_key,
            )
    except (OSError, RuntimeError) as exc:
        print(f"[FATAL] Could not acquire Publisher queue ownership: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
