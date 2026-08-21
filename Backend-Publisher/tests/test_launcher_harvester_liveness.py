import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_DIR = REPO_ROOT / "Backend-Publisher"
HARVESTER_DIR = REPO_ROOT / "Backend-Harvester"
LAUNCHER = REPO_ROOT / "Infrastructure" / "Run-LMN-Batch.ps1"
LIVENESS_HELPER = REPO_ROOT / "Infrastructure" / "Lmn-LivenessBoundary.ps1"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


publisher = _load_module("lmn_publisher_liveness", PUBLISHER_DIR / "main.py")
publisher_spool = _load_module("lmn_publisher_spool_liveness", PUBLISHER_DIR / "spool.py")
harvester_claim = _load_module("lmn_harvester_claim_liveness", HARVESTER_DIR / "queue_claim.py")


def _valid_item(source_url, title):
    return {
        "category": "AI",
        "source_name": "Example",
        "source_url": source_url,
        "title_en": title,
        "title_pt": title,
        "summary_en": f"{title} summary",
        "summary_pt": f"{title} resumo",
    }


class _FakeQuery:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.items = []

    def upsert(self, item, **_kwargs):
        self.items.append(item)
        return self

    def execute(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(data=outcome)


class _FakeClient:
    def __init__(self, outcomes):
        self.query = _FakeQuery(outcomes)

    def table(self, name):
        assert name == "news"
        return self.query


def _transient_failures(count=3):
    request = httpx.Request("POST", "https://example.supabase.co")
    return [httpx.ConnectError("offline", request=request) for _ in range(count)]


def _launcher_gate_allows(preflight_exit):
    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "Publisher CI must provide PowerShell Core for the launcher boundary regression"
    helper = str(LIVENESS_HELPER).replace("'", "''")
    command = (
        f". '{helper}'; "
        f"if (Test-LmnPublisherPreflightAllowsHarvester -PublisherExit {int(preflight_exit)}) "
        "{ exit 0 } else { exit 23 }"
    )
    completed = subprocess.run(
        [pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode not in {0, 23}:
        raise AssertionError(
            "PowerShell launcher gate harness failed unexpectedly: "
            f"exit={completed.returncode}, stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        )
    return completed.returncode == 0


def _configure_publisher(monkeypatch, input_file, retry_file, rejected_file):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-server-key")
    monkeypatch.setenv("LMN_INPUT_FILE", str(input_file))
    monkeypatch.setenv("LMN_RETRY_FILE", str(retry_file))
    monkeypatch.setenv("LMN_REJECTED_FILE", str(rejected_file))
    monkeypatch.setattr(publisher, "RETRY_BACKOFF_SECONDS", 0)


def test_launcher_uses_extracted_preflight_gate_before_harvester():
    text = LAUNCHER.read_text(encoding="utf-8")
    preflight = text.index("$preflightExit = Invoke-PublisherDrain")
    gate = text.index(
        "Test-LmnPublisherPreflightAllowsHarvester -PublisherExit $preflightExit"
    )
    harvester = text.index("[4/6] Triggering LMN-Harvester")

    assert "$LivenessBoundaryHelperSource" in text
    assert ". $LivenessBoundaryHelperSource" in text
    assert preflight < gate < harvester


def test_launcher_harvester_liveness_retained_a_cannot_starve_handoff_b(monkeypatch, tmp_path):
    retry_file = tmp_path / "publisher" / "retry.json"
    rejected_file = tmp_path / "publisher" / "rejected.json"
    run_n_input = tmp_path / "publisher" / "run-n-a.json"
    no_inbound = tmp_path / "publisher-spool" / "processing" / "__no_inbound__.json"
    spool_root = tmp_path / "publisher-spool"
    harvester_pending = tmp_path / "harvester" / "news_to_publish.json"
    staging_dir = tmp_path / "publisher-staging"
    item_a = _valid_item("https://example.com/a", "A")
    item_b = _valid_item("https://example.com/b", "B")

    _configure_publisher(monkeypatch, run_n_input, retry_file, rejected_file)

    # RUN N: A exhausts the bounded in-process attempts but the scheduler-facing
    # Publisher result remains success while the retry is durably retained.
    run_n_input.parent.mkdir(parents=True, exist_ok=True)
    run_n_input.write_text(json.dumps([item_a]), encoding="utf-8")
    run_n_client = _FakeClient(_transient_failures())
    monkeypatch.setattr(publisher, "create_client", lambda *_: run_n_client)
    assert publisher.main() == 0
    assert len(run_n_client.query.items) == publisher.MAX_ATTEMPTS
    retained_before = json.loads(retry_file.read_text(encoding="utf-8"))[0]
    metadata_before = retained_before[publisher.RETRY_METADATA_KEY]
    remaining_budget_before = publisher.MAX_RETRY_CYCLES - metadata_before["cycles"]
    assert metadata_before["cycles"] == 1
    assert metadata_before["first_failed_at"] is not None
    assert metadata_before["next_attempt_at"] > metadata_before["first_failed_at"]

    # RUN N+1 preflight: use the launcher's absent-input convention. A is not due,
    # so there are zero provider calls and its persisted retry budget is byte-for-byte
    # equivalent at the JSON object level.
    _configure_publisher(monkeypatch, no_inbound, retry_file, rejected_file)
    preflight_client = _FakeClient([])
    monkeypatch.setattr(publisher, "create_client", lambda *_: preflight_client)
    preflight_exit = publisher.main()
    assert preflight_exit == 0
    assert preflight_client.query.items == []
    retained_after_preflight = json.loads(retry_file.read_text(encoding="utf-8"))[0]
    assert retained_after_preflight == retained_before
    assert (
        publisher.MAX_RETRY_CYCLES
        - retained_after_preflight[publisher.RETRY_METADATA_KEY]["cycles"]
        == remaining_budget_before
    )

    # Exercise the exact launcher-level decision used by Run-LMN-Batch.ps1. The
    # historical retained-work non-zero result is the control: it must stop here.
    assert _launcher_gate_allows(preflight_exit)
    assert not _launcher_gate_allows(1)

    # The Harvester independently produces B. Follow the supported ownership handoff:
    # pending -> immutable Harvester claim -> staging -> immutable Publisher inbox.
    harvester_pending.parent.mkdir(parents=True, exist_ok=True)
    harvester_pending.write_text(json.dumps([item_b]), encoding="utf-8")
    batch_id = "batch-" + ("b" * 32)
    claim_path = harvester_claim.claim_pending_batch(
        harvester_pending,
        batch_id_factory=lambda: batch_id,
    )
    assert claim_path is not None
    assert not harvester_pending.exists()
    assert json.loads(claim_path.read_text(encoding="utf-8")) == [item_b]

    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f"{batch_id}-transfer.json"
    shutil.copyfile(claim_path, staging_path)
    owned_b = publisher_spool.enqueue_staged_batch(staging_path, spool_root, batch_id)
    expected_inbox_b = spool_root / "inbox" / f"{batch_id}.json"
    assert owned_b == expected_inbox_b
    assert expected_inbox_b.exists()
    assert json.loads(expected_inbox_b.read_text(encoding="utf-8")) == [item_b]
    assert harvester_claim.complete_claim(harvester_pending, batch_id)
    assert not claim_path.exists()

    # Handoff itself cannot consume or reset A's retry lifetime.
    retained_after_handoff = json.loads(retry_file.read_text(encoding="utf-8"))[0]
    assert retained_after_handoff == retained_before

    # The launcher's later Publisher drain claims B from the real spool protocol.
    # A is still deferred, therefore the only provider call is for B.
    claimed_b = publisher_spool.claim_next_batch(spool_root)
    assert claimed_b == spool_root / "processing" / f"{batch_id}.json"
    _configure_publisher(monkeypatch, claimed_b, retry_file, rejected_file)
    b_client = _FakeClient([[{"id": 2}]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: b_client)
    assert publisher.main() == 0
    assert [item["source_url"] for item in b_client.query.items] == [item_b["source_url"]]
    assert not claimed_b.exists()
    assert not rejected_file.exists()

    retained_final = json.loads(retry_file.read_text(encoding="utf-8"))[0]
    metadata_final = retained_final[publisher.RETRY_METADATA_KEY]
    assert retained_final == retained_before
    assert metadata_final["cycles"] == metadata_before["cycles"]
    assert metadata_final["first_failed_at"] == metadata_before["first_failed_at"]
    assert metadata_final["next_attempt_at"] == metadata_before["next_attempt_at"]
    assert publisher.MAX_RETRY_CYCLES - metadata_final["cycles"] == remaining_budget_before
