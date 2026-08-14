import importlib.util
import socket
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("lmn_harvester_ssrf", MODULE_PATH)
harvester = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(harvester)

PUBLIC_IP = "93.184.216.34"


def resolver(mapping):
    def resolve(host, port, type=socket.SOCK_STREAM):
        address = mapping[host]
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
        ]

    return resolve


class Response:
    def __init__(self, status_code=200, *, location=None, content=None):
        self.status_code = status_code
        self.headers = {} if location is None else {"Location": location}
        self.content = content or b"<rss><channel><title>Source</title></channel></rss>"

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, timeout, allow_redirects):
        self.calls.append((url, timeout, allow_redirects))
        if not self.responses:
            pytest.fail(f"unexpected network contact: {url}")
        return self.responses.pop(0)


def test_public_feed_succeeds_without_automatic_redirects():
    session = Session([Response()])
    parsed = harvester.fetch_feed(
        "https://public.example/feed",
        session=session,
        resolver=resolver({"public.example": PUBLIC_IP}),
    )

    assert parsed.feed.title == "Source"
    assert session.calls == [
        ("https://public.example/feed", harvester.SOURCE_TIMEOUT_SECONDS, False)
    ]


@pytest.mark.parametrize(
    ("target", "address"),
    [
        ("http://loopback.example/feed", "127.0.0.1"),
        ("http://private.example/feed", "10.0.0.5"),
        ("http://metadata.example/latest/meta-data", "169.254.169.254"),
        ("http://ipv6-loop.example/feed", "::1"),
        ("http://ipv6-linklocal.example/feed", "fe80::1"),
    ],
)
def test_non_public_initial_target_is_never_contacted(monkeypatch, target, address):
    session = Session([])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed(
            target,
            session=session,
            resolver=resolver({target.split("//", 1)[1].split("/", 1)[0]: address}),
        )

    assert session.calls == []


@pytest.mark.parametrize(
    ("redirect_url", "redirect_host", "address"),
    [
        ("http://loopback.example/admin", "loopback.example", "127.0.0.1"),
        ("http://private.example/admin", "private.example", "10.0.100.20"),
        (
            "http://metadata.example/latest/meta-data",
            "metadata.example",
            "169.254.169.254",
        ),
        ("http://ipv6-loop.example/admin", "ipv6-loop.example", "::1"),
        ("http://ipv6-link.example/admin", "ipv6-link.example", "fe80::1"),
    ],
)
def test_redirect_to_non_public_target_is_rejected_before_contact(
    monkeypatch, redirect_url, redirect_host, address
):
    responses = [
        Response(302, location=redirect_url) for _ in range(harvester.MAX_RETRIES + 1)
    ]
    session = Session(responses)
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)
    resolve = resolver({"public.example": PUBLIC_IP, redirect_host: address})

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed("https://public.example/feed", session=session, resolver=resolve)

    assert [call[0] for call in session.calls] == [
        "https://public.example/feed"
    ] * (harvester.MAX_RETRIES + 1)
    assert all(redirect_host not in call[0] for call in session.calls)


def test_hostname_resolving_private_is_rejected_without_contact(monkeypatch):
    session = Session([])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed(
            "https://ordinary-name.example/feed",
            session=session,
            resolver=resolver({"ordinary-name.example": "192.168.1.20"}),
        )

    assert session.calls == []


def test_redirect_count_is_bounded(monkeypatch):
    total_requests = (harvester.MAX_REDIRECTS + 1) * (harvester.MAX_RETRIES + 1)
    session = Session([Response(302, location="/again") for _ in range(total_requests)])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="redirect limit exceeded"):
        harvester.fetch_feed(
            "https://public.example/feed",
            session=session,
            resolver=resolver({"public.example": PUBLIC_IP}),
        )

    assert len(session.calls) == total_requests
