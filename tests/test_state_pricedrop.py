import pytest

from marktplaats_monitor.models import EventKind
from marktplaats_monitor.state import StateStore
from tests.conftest import make_listing


@pytest.fixture
def store(tmp_path):
    s = StateStore(tmp_path / "state.sqlite3")
    s.ensure_search("s1", "S1")
    yield s
    s.close()


def _seed_known(store, cents):
    """Insert a listing and mark its NEW notified so it's a known listing."""
    store.process_listings("s1", "S1", [make_listing("m1", cents=cents)], seeding=False)
    store.mark_new_notified("s1", "m1")


def test_price_drop_emitted_once(store):
    _seed_known(store, 10000)
    events = store.process_listings("s1", "S1", [make_listing("m1", cents=8000)], seeding=False)
    assert [e.kind for e in events] == [EventKind.PRICE_DROP]
    e = events[0]
    assert e.old_price_cents == 10000
    assert e.new_price_cents == 8000

    store.mark_drop_notified("s1", "m1", 8000)
    # same lowered price again -> no repeat
    assert store.process_listings("s1", "S1", [make_listing("m1", cents=8000)], seeding=False) == []


def test_further_drop_below_floor_re_emits(store):
    _seed_known(store, 10000)
    store.process_listings("s1", "S1", [make_listing("m1", cents=8000)], seeding=False)
    store.mark_drop_notified("s1", "m1", 8000)

    events = store.process_listings("s1", "S1", [make_listing("m1", cents=7000)], seeding=False)
    assert [e.kind for e in events] == [EventKind.PRICE_DROP]
    assert events[0].new_price_cents == 7000


def test_price_increase_does_not_emit(store):
    _seed_known(store, 10000)
    assert (
        store.process_listings("s1", "S1", [make_listing("m1", cents=12000)], seeding=False) == []
    )


def test_non_numeric_price_ignored(store):
    _seed_known(store, 10000)
    # listing flips to "Bieden" (cents None) -> no drop event
    assert store.process_listings("s1", "S1", [make_listing("m1", cents=None)], seeding=False) == []


def test_no_drop_when_unchanged(store):
    _seed_known(store, 10000)
    assert (
        store.process_listings("s1", "S1", [make_listing("m1", cents=10000)], seeding=False) == []
    )
