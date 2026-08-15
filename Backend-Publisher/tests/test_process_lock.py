import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("lmn_publisher_lock", MODULE_PATH)
publisher = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(publisher)


def configured_paths(tmp_path):
    input_file = tmp_path / "inbound.json"
    retry_file = tmp_path / "retry.json"
    rejected_file = tmp_path / "rejected.json"
    lock_file = publisher.get_queue_lock_path(input_file, retry_file, rejected_file)
    return input_file, retry_file, rejected_file, lock_file


def test_queue_lock_is_distinct_and_tied_to_retry_ownership(tmp_path):
    input_file, retry_file, rejected_file, lock_file = configured_paths(tmp_path)

    assert lock_file == tmp_path / ".retry.json.lock"
    assert lock_file not in {input_file, retry_file, rejected_file}


def test_second_publisher_owner_fails_closed_and_lock_can_be_reacquired(tmp_path):
    _, _, _, lock_file = configured_paths(tmp_path)

    with publisher.publisher_queue_lock(lock_file):
        with pytest.raises(RuntimeError, match="already owns this queue set"):
            with publisher.publisher_queue_lock(lock_file):
                pytest.fail("second owner must never enter the queue critical section")

    with publisher.publisher_queue_lock(lock_file):
        pass


def test_main_refuses_overlap_before_reading_or_mutating_queue(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file, lock_file = configured_paths(tmp_path)
    inbound = [{"sentinel": "must remain untouched"}]
    input_file.write_text(json.dumps(inbound), encoding="utf-8")

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-server-key")
    monkeypatch.setenv("LMN_INPUT_FILE", str(input_file))
    monkeypatch.setenv("LMN_RETRY_FILE", str(retry_file))
    monkeypatch.setenv("LMN_REJECTED_FILE", str(rejected_file))
    monkeypatch.setattr(
        publisher,
        "create_client",
        lambda *_: pytest.fail("overlapping owner must fail before creating a client"),
    )

    with publisher.publisher_queue_lock(lock_file):
        assert publisher.main() == 1

    assert json.loads(input_file.read_text(encoding="utf-8")) == inbound
    assert not retry_file.exists()
    assert not rejected_file.exists()
