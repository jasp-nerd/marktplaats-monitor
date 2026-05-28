import pytest

from marktplaats_monitor.config import Config, NotifyConfig, SearchConfig
from marktplaats_monitor.models import EventKind
from marktplaats_monitor.monitor import Monitor
from marktplaats_monitor.state import StateStore
from tests.conftest import make_listing


class FakeNotifier:
    def __init__(self, succeed=True):
        self.succeed = succeed
        self.events = []

    def send_event(self, event, **kwargs):
        self.events.append(event)
        return self.succeed


def _config(seed=True):
    s = SearchConfig(
        id="s1",
        name="HomePod",
        url="https://www.marktplaats.nl/q/homepod/",
        seed_without_notify=seed,
        notify=NotifyConfig(backend="apprise"),
    )
    return Config(check_interval=60, searches=[s])


@pytest.fixture
def monitor(tmp_path):
    store = StateStore(tmp_path / "s.sqlite3")
    m = Monitor(_config(), store)
    yield m, store
    m.close()
    store.close()


def _patch(rt, listings, notifier):
    rt.client.search = lambda *a, **k: list(listings)
    rt.notifier = notifier


def test_seed_then_notify_new_then_silent(monitor):
    m, store = monitor
    rt = m.runtimes[0]
    fn = FakeNotifier()
    _patch(rt, [make_listing("A", cents=10000)], fn)

    # cycle 1: seeding -> no notifications
    m.run_search(rt)
    assert fn.events == []

    # cycle 2: A known + new listing B -> only B notified
    _patch(rt, [make_listing("A", cents=10000), make_listing("B", cents=5000)], fn)
    m.run_search(rt)
    assert [e.listing.item_id for e in fn.events] == ["B"]
    assert fn.events[0].kind is EventKind.NEW

    # cycle 3: nothing new -> silent
    fn.events.clear()
    m.run_search(rt)
    assert fn.events == []


def test_price_drop_flow(monitor):
    m, store = monitor
    rt = m.runtimes[0]
    fn = FakeNotifier()

    _patch(rt, [make_listing("A", cents=10000)], fn)
    m.run_search(rt)  # seed
    _patch(rt, [make_listing("A", cents=10000)], fn)
    m.run_search(rt)  # known, still no event

    _patch(rt, [make_listing("A", cents=7000)], fn)
    m.run_search(rt)
    assert len(fn.events) == 1
    e = fn.events[0]
    assert e.kind is EventKind.PRICE_DROP
    assert e.old_price_cents == 10000 and e.new_price_cents == 7000


def test_failed_send_retries_next_cycle(monitor):
    m, store = monitor
    rt = m.runtimes[0]

    _patch(rt, [make_listing("A")], FakeNotifier())
    m.run_search(rt)  # seed A

    failing = FakeNotifier(succeed=False)
    _patch(rt, [make_listing("A"), make_listing("B")], failing)
    m.run_search(rt)
    assert [e.listing.item_id for e in failing.events] == ["B"]  # tried, failed

    ok = FakeNotifier(succeed=True)
    _patch(rt, [make_listing("A"), make_listing("B")], ok)
    m.run_search(rt)
    assert [e.listing.item_id for e in ok.events] == ["B"]  # retried, succeeded

    ok.events.clear()
    _patch(rt, [make_listing("A"), make_listing("B")], ok)
    m.run_search(rt)
    assert ok.events == []  # now silent


def test_filter_drops_listing(monitor):
    m, store = monitor
    rt = m.runtimes[0]
    rt.filter = rt.search.listing_filter()  # no filters -> passes
    rt.search.exclude_keywords = ["kapot"]
    rt.filter = rt.search.listing_filter()
    fn = FakeNotifier()
    _patch(rt, [make_listing("A", title="iPhone kapot")], fn)
    # not seeding here would still record; seeding suppresses. Force non-seed:
    store.ensure_search("s1", "HopePod")
    store.mark_run_complete("s1")
    _patch(rt, [make_listing("A", title="iPhone kapot")], fn)
    m.run_search(rt)
    assert fn.events == []  # filtered out before state


def test_run_once_returns_zero(monitor):
    m, _ = monitor
    rt = m.runtimes[0]
    _patch(rt, [make_listing("A")], FakeNotifier())
    assert m.run_once() == 0
