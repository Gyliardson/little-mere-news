#!/usr/bin/env python3
"""Immutable Publisher inbound spool with crash-safe claiming.

Producers never replace a mutable consumer input path. Every transferred Harvester
batch is installed under a unique batch id in ``inbox/``. A consumer atomically
renames exactly one inbox file to ``processing/`` and invokes ``main.py`` with that
claimed path as LMN_INPUT_FILE. New batches may arrive concurrently and cannot be
removed when the older processing file is completed.
"""

import argparse
import errno
import fcntl
import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

BATCH_ID_RE = re.compile(r"^batch-[0-9a-f]{32}$")


def validate_batch_id(batch_id):
    if not isinstance(batch_id, str) or not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("invalid Publisher batch id")
    return batch_id


def spool_paths(spool_root):
    root = Path(spool_root)
    return root, root / "inbox", root / "processing"


def spool_lock_path(spool_root):
    root = Path(spool_root)
    return root / ".claim.lock"


@contextmanager
def spool_claim_lock(spool_root):
    root, _, _ = spool_paths(spool_root)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = spool_lock_path(root)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _read_valid_batch_bytes(path):
    data = Path(path).read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Publisher staged batch must be a JSON array")
    return data


def _existing_batch_path(spool_root, batch_id):
    _, inbox, processing = spool_paths(spool_root)
    name = f"{batch_id}.json"
    for directory in (processing, inbox):
        path = directory / name
        if path.exists():
            return path
    return None


def enqueue_staged_batch(staging_path, spool_root, batch_id, before_publish_hook=None):
    """Install a complete immutable batch into inbox without overwriting another batch.

    Bytes are fsynced to a same-directory temporary file and then hard-linked into the
    final inbox name. ``os.link`` is the non-overwriting atomic publish primitive: an
    existing final name is never replaced. Crash leftovers use a dot-prefixed ``.tmp``
    name and are ignored by consumers.
    """

    batch_id = validate_batch_id(batch_id)
    staging = Path(staging_path)
    root, inbox, processing = spool_paths(spool_root)
    inbox.mkdir(parents=True, exist_ok=True)
    processing.mkdir(parents=True, exist_ok=True)
    data = _read_valid_batch_bytes(staging)

    existing = _existing_batch_path(root, batch_id)
    if existing is not None:
        if existing.read_bytes() != data:
            raise ValueError(f"batch id collision with different content: {batch_id}")
        staging.unlink(missing_ok=True)
        return existing

    final_path = inbox / f"{batch_id}.json"
    temp_path = inbox / f".{batch_id}.{uuid.uuid4().hex}.tmp"
    installed = False
    try:
        with temp_path.open("xb") as file_handle:
            file_handle.write(data)
            file_handle.flush()
            os.fsync(file_handle.fileno())

        if before_publish_hook is not None:
            before_publish_hook(temp_path, final_path)

        try:
            os.link(temp_path, final_path)
            installed = True
        except FileExistsError:
            if final_path.read_bytes() != data:
                raise ValueError(f"batch id collision with different content: {batch_id}")
            installed = True

        staging.unlink(missing_ok=True)
        return final_path
    finally:
        temp_path.unlink(missing_ok=True)
        if not installed:
            # The caller retains staging for a later retry. The consumer never sees a
            # partially written final JSON batch.
            pass


def _processing_batches(processing):
    return sorted(path for path in processing.glob("batch-*.json") if path.is_file())


def _inbox_batches(inbox):
    return sorted(path for path in inbox.glob("batch-*.json") if path.is_file())


def claim_next_batch(spool_root):
    """Return one exact processing file, recovering a crash claim before new inbox work."""

    root, inbox, processing = spool_paths(spool_root)
    inbox.mkdir(parents=True, exist_ok=True)
    processing.mkdir(parents=True, exist_ok=True)

    with spool_claim_lock(root):
        # A process killed after atomic claim but before Publisher completion leaves the
        # batch here. Recovery always resumes it before claiming new work.
        existing = _processing_batches(processing)
        if existing:
            return existing[0]

        queued = _inbox_batches(inbox)
        if not queued:
            return None

        source = queued[0]
        claimed = processing / source.name
        os.replace(source, claimed)
        return claimed


def batch_id_from_path(batch_path):
    path = Path(batch_path)
    if path.suffix != ".json":
        raise ValueError("Publisher batch path must end in .json")
    return validate_batch_id(path.stem)


def build_parser():
    parser = argparse.ArgumentParser(description="Publisher immutable inbound spool helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enqueue = subparsers.add_parser("enqueue")
    enqueue.add_argument("--staging", required=True)
    enqueue.add_argument("--spool", required=True)
    enqueue.add_argument("--batch-id", required=True)

    claim = subparsers.add_parser("claim-next")
    claim.add_argument("--spool", required=True)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "enqueue":
            final_path = enqueue_staged_batch(args.staging, args.spool, args.batch_id)
            print(final_path)
            return 0
        if args.command == "claim-next":
            claimed = claim_next_batch(args.spool)
            if claimed is not None:
                print(claimed)
            return 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ERROR] Publisher spool operation failed: {type(exc).__name__}: {exc}")
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
