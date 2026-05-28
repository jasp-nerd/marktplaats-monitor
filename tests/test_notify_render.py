import pytest

from marktplaats_monitor.models import EventKind, NotifyEvent
from marktplaats_monitor.notify import Notifier
from marktplaats_monitor.notify.apprise_sink import AppriseSink
from marktplaats_monitor.notify.discord_embed import (
    build_discord_payload,
    resolve_mention,
    send_discord,
)
from marktplaats_monitor.notify.render import build_body, build_title
from tests.conftest import make_listing


def _new_event():
    return NotifyEvent(EventKind.NEW, make_listing("m1", cents=9000), "s1", "HomePod mini")


def _drop_event():
    return NotifyEvent(
        EventKind.PRICE_DROP,
        make_listing("m1", cents=7000),
        "s1",
        "HomePod mini",
        old_price_cents=10000,
        new_price_cents=7000,
    )


# -- render -----------------------------------------------------------------


def test_titles():
    assert build_title(_new_event()).startswith("🆕")
    assert "Prijsverlaging" in build_title(_drop_event())


def test_body_new_has_price_and_link():
    body = build_body(_new_event())
    assert "**Test listing**" in body
    assert "🔗 https://link.marktplaats.nl/m1" in body
    assert "@everyone" not in body  # mention is never baked into render


def test_body_drop_shows_old_to_new():
    body = build_body(_drop_event())
    assert "€ 100,00 → € 70,00" in body


# -- mentions ---------------------------------------------------------------


@pytest.mark.parametrize(
    "mention,expected_content,expected_allowed",
    [
        ("none", None, {"parse": []}),
        ("everyone", "@everyone", {"parse": ["everyone"]}),
        ("here", "@here", {"parse": ["everyone"]}),
        ("role:12345", "<@&12345>", {"roles": ["12345"]}),
    ],
)
def test_resolve_mention(mention, expected_content, expected_allowed):
    content, allowed = resolve_mention(mention)
    assert content == expected_content
    assert allowed == expected_allowed


# -- discord embed ----------------------------------------------------------


def test_build_discord_payload_new():
    p = build_discord_payload(_new_event(), mention="none")
    assert "content" not in p
    assert p["allowed_mentions"] == {"parse": []}
    embed = p["embeds"][0]
    assert embed["color"] == 0x1E90FF
    assert embed["image"]["url"].startswith("https://images.marktplaats.com")


def test_build_discord_payload_drop_and_mention():
    p = build_discord_payload(_drop_event(), mention="everyone")
    assert p["content"] == "@everyone"
    assert p["allowed_mentions"] == {"parse": ["everyone"]}
    assert "~~" in p["embeds"][0]["fields"][0]["value"]  # struck-through old price
    assert p["embeds"][0]["color"] == 0x2ECC71


# -- send_discord -----------------------------------------------------------


class FakePost:
    def __init__(self, status, headers=None, text=""):
        self.status_code = status
        self.headers = headers or {}
        self.text = text


def test_send_discord_success(monkeypatch):

    sess = type("S", (), {"post": lambda self, *a, **k: FakePost(204)})()
    assert send_discord("http://wh", {"x": 1}, session=sess) is True


def test_send_discord_retry_then_success(monkeypatch):
    import marktplaats_monitor.notify.discord_embed as de

    monkeypatch.setattr(de.time, "sleep", lambda *_: None)
    seq = [FakePost(429, {"Retry-After": "0"}), FakePost(204)]
    sess = type("S", (), {"post": lambda self, *a, **k: seq.pop(0)})()
    assert send_discord("http://wh", {}, session=sess, max_retries=2) is True


def test_send_discord_hard_failure():
    sess = type("S", (), {"post": lambda self, *a, **k: FakePost(400, text="bad")})()
    assert send_discord("http://wh", {}, session=sess) is False


# -- AppriseSink ------------------------------------------------------------


class FakeApprise:
    def __init__(self):
        self.added = []
        self.calls = []

    def add(self, url, tag=None):
        self.added.append((url, tag))
        return "bad" not in url

    def notify(self, **kwargs):
        self.calls.append(kwargs)
        return True


def test_apprise_sink_adds_and_counts():
    fake = FakeApprise()
    sink = AppriseSink(
        [("discord://a/b", ["listings"]), ("bad://x", ["listings"])],
        apprise_factory=lambda: fake,
    )
    assert sink.has_targets
    assert fake.added[0] == ("discord://a/b", ["listings"])


def test_apprise_sink_notify_prepends_mention_and_passes_args():
    fake = FakeApprise()
    sink = AppriseSink([("ntfy://topic", ["listings"])], apprise_factory=lambda: fake)
    ok = sink.notify("T", "B", tag="listings", attach="http://img", mention="everyone")
    assert ok is True
    call = fake.calls[0]
    assert call["body"].startswith("@everyone\n")
    assert call["tag"] == "listings"
    assert call["attach"] == "http://img"
    assert call["body_format"] == "markdown"


# -- Notifier routing -------------------------------------------------------


def test_notifier_apprise_backend():
    fake = FakeApprise()
    sink = AppriseSink([("ntfy://t", ["listings"])], apprise_factory=lambda: fake)
    n = Notifier(apprise_sink=sink)
    assert n.send_event(_new_event(), backend="apprise") is True
    assert fake.calls[0]["tag"] == "listings"


def test_notifier_discord_native(monkeypatch):
    import marktplaats_monitor.notify as nmod

    sent = {}
    monkeypatch.setattr(
        nmod, "send_discord", lambda url, payload, **k: sent.update(payload) or True
    )
    n = Notifier(discord_webhook="http://wh")
    assert n.send_event(_new_event(), backend="discord_native", mention="here") is True
    assert sent["content"] == "@here"


def test_notifier_apprise_without_targets_fails():
    n = Notifier(apprise_sink=None)
    assert n.send_event(_new_event(), backend="apprise") is False
