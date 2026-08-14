#!/usr/bin/env python3
"""Crash-safe ownership helper for the Harvester pending handoff.

The Harvester itself owns a mutable *pending* file while collecting/merging new work.
The launcher must never copy that file and later unlink it directly. Instead it asks
this helper to atomically rename the current pending file into an immutable claim.
New Harvester writes then create/merge a new pending file and cannot be removed when
an older claim is acknowledged.
"""

import argparse
import fcntl
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

BATCH_ID_RE = re.compile(r"^batch-[0-9a-f]{32}$")


def pending_lock_path(pending_path):
    pending = Path(pending_path)
    return pending.with_name(f".{pending.name}.lock")


def claims_dir_for(pending_path):
    pending = Path(pending_path)
    return pending.parent / ".lmn-harvester-claims"


@contextmanager
def pending_owner_lock(pending_path):
    lock_path = pending_lock_path(pending_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _claimed_batches(pending_path):
    claims_dir = claims_dir_for(pending_path)
    if not claims_dir.exists():
        return []
    return sorted(
        (path for path in claims_dir.glob("batch-*.json") if path.is_file()),
        key=lambda path: path.name,
    )


def claim_pending_batch(pending_path, batch_id_factory=None):
    """Return one durable claim, atomically creating it from pending when needed.

    A pre-existing claim is returned first. That is the crash-recovery rule: a
    launcher that dies after claim but before acknowledgement leaves the exact batch
    detectable for the next invocation.
    """

    pending = Path(pending_path)
    batch_id_factory = batch_id_factory or (lambda: f"batch-{uuid.uuid4().hex}")

    with pending_owner_lock(pending):
        existing = _claimed_batches(pending)
        if existing:
            return existing[0]
        if not pending.exists():
            return None

        claims_dir = claims_dir_for(pending)
        claims_dir.mkdir(parents=True, exist_ok=True)
        batch_id = batch_id_factory()
        if not BATCH_ID_RE.fullmatch(batch_id):
            raise ValueError("invalid Harvester batch id")
        claim_path = claims_dir / f"{batch_id}.json"
        if claim_path.exists():
            raise FileExistsError(f"Harvester claim already exists: {claim_path}")

        # Same-filesystem rename is the ownership transfer. Once this succeeds the
        # launcher owns only claim_path; a later Harvester writes a fresh pending file.
        os.replace(pending, claim_path)
        return claim_path


def complete_claim(pending_path, batch_id):
    """Acknowledge only the exact immutable claim identified by batch_id."""

    if not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("invalid Harvester batch id")
    pending = Path(pending_path)
    claim_path = claims_dir_for(pending) / f"{batch_id}.json"
    with pending_owner_lock(pending):
        if not claim_path.exists():
            return False
        claim_path.unlink()
        return True


def batch_id_from_claim(claim_path):
    path = Path(claim_path)
    if path.suffix != ".json":
        raise ValueError("claim path must be a JSON batch")
    batch_id = path.stem
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("invalid Harvester claim filename")
    return batch_id


def build_parser():
    parser = argparse.ArgumentParser(description="Harvester pending queue ownership helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    claim = subparsers.add_parser("claim")
    claim.add_argument("--pending", required=True)

    complete = subparsers.add_parser("complete")
    complete.add_argument("--pending", required=True)
    complete.add_argument("--batch-id", required=True)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "claim":
            claim_path = claim_pending_batch(args.pending)
            if claim_path is not None:
                print(claim_path)
            return 0
        if args.command == "complete":
            if not complete_claim(args.pending, args.batch_id):
                print(f"[ERROR] Harvester claim not found: {args.batch_id}")
                return 1
            return 0
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Harvester ownership operation failed: {type(exc).__name__}: {exc}")
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
