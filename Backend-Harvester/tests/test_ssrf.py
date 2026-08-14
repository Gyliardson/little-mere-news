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
SECOND_PUBLIC_IP = "93.184.216.35"


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
        if self.status_code >= 400:
            raise harvester.FeedTransportError(f"HTTP {self.status_code}")


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, address):
        self.calls.append((url, str(address)))
        if not self.responses:
            pytest.fail(f"unexpected network contact: {url} -> {address}")
        return self.responses.pop(0)


def test_public_feed_is_contacted_only_at_validated_ip():
    transport = Transport([Response()])
    parsed = harvester.fetch_feed(
        "https://public.example/feed",
        transport=transport,
        resolver=resolver({"public.example": PUBLIC_IP}),
    )

    assert parsed.feed.title == "Source"
    assert transport.calls == [("https://public.example/feed", PUBLIC_IP)]


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
    transport = Transport([])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed(
            target,
            transport=transport,
            resolver=resolver({target.split("//", 1)[1].split("/", 1)[0]: address}),
        )

    assert transport.calls == []


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
    transport = Transport(responses)
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)
    resolve = resolver({"public.example": PUBLIC_IP, redirect_host: address})

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed(
            "https://public.example/feed",
            transport=transport,
            resolver=resolve,
        )

    assert transport.calls == [
        ("https://public.example/feed", PUBLIC_IP)
    ] * (harvester.MAX_RETRIES + 1)


def test_hostname_resolving_private_is_rejected_without_contact(monkeypatch):
    transport = Transport([])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="forbidden non-public"):
        harvester.fetch_feed(
            "https://ordinary-name.example/feed",
            transport=transport,
            resolver=resolver({"ordinary-name.example": "192.168.1.20"}),
        )

    assert transport.calls == []


def test_dns_answer_is_pinned_for_each_request_and_cannot_rebind_inside_transport():
    answers = iter([PUBLIC_IP, SECOND_PUBLIC_IP])

    def changing_resolver(host, port, type=socket.SOCK_STREAM):
        address = next(answers)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    transport = Transport([Response(302, location="/next"), Response()])
    parsed = harvester.fetch_feed(
        "https://rebind.example/feed",
        transport=transport,
        resolver=changing_resolver,
    )

    assert parsed.feed.title == "Source"
    assert transport.calls == [
        ("https://rebind.example/feed", PUBLIC_IP),
        ("https://rebind.example/next", SECOND_PUBLIC_IP),
    ]


def test_transport_never_receives_hostname_as_connection_destination():
    transport = Transport([Response()])
    harvester.fetch_feed(
        "https://public.example/feed",
        transport=transport,
        resolver=resolver({"public.example": PUBLIC_IP}),
    )

    assert transport.calls[0][1] == PUBLIC_IP
    assert transport.calls[0][1] != "public.example"


def test_pinned_https_dials_approved_ip_but_verifies_original_hostname(monkeypatch):
    events = {}
    raw_socket = object()
    wrapped_socket = object()

    def fake_connect(connection):
        events["dial_host"] = connection.host
        connection.sock = raw_socket

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            events["wrapped_socket"] = sock
            events["server_hostname"] = server_hostname
            return wrapped_socket

    monkeypatch.setattr(harvester.http.client.HTTPConnection, "connect", fake_connect)
    connection = harvester.PinnedHTTPSConnection(
        address=PUBLIC_IP,
        hostname="public.example",
        port=443,
        timeout=harvester.SOURCE_TIMEOUT_SECONDS,
    )
    connection._context = FakeContext()

    connection.connect()

    assert events == {
        "dial_host": PUBLIC_IP,
        "wrapped_socket": raw_socket,
        "server_hostname": "public.example",
    }
    assert connection.host == "public.example"
    assert connection.sock is wrapped_socket


def test_redirect_count_is_bounded(monkeypatch):
    total_requests = (harvester.MAX_REDIRECTS + 1) * (harvester.MAX_RETRIES + 1)
    transport = Transport([Response(302, location="/again") for _ in range(total_requests)])
    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="redirect limit exceeded"):
        harvester.fetch_feed(
            "https://public.example/feed",
            transport=transport,
            resolver=resolver({"public.example": PUBLIC_IP}),
        )

    assert len(transport.calls) == total_requests
