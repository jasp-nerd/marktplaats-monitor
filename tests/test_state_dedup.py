import pytest

from marktplaats_monitor.models import EventKind
from marktplaats_monitor.state import StateStore
from tests.conftest import make_listing


@pytest.fixture
def store(tmp_path):
    s = StateStore(tmp_path / "state.sqlite3")
    yield s
    s.close()


def test_ensure_search_seeding_then_not(store):
    assert store.ensure_search("s1", "Search 1") is True
    store.mark_run_complete("s1")
    assert store.ensure_search("s1", "Search 1") is False


def test_new_listing_emits_then_silent_after_mark(store):
    store.ensure_search("s1", "S1")
    lst = make_listing("m1")

    events = store.process_listings("s1", "S1", [lst], seeding=False)
    assert [e.kind for e in events] == [EventKind.NEW]

    store.mark_new_notified("s1", "m1")
    events = store.process_listings("s1", "S1", [lst], seeding=False)
    assert events == []


def test_new_listing_reemitted_until_notified(store):
    store.ensure_search("s1", "S1")
    lst = make_listing("m1")

    # send "failed": we never call mark_new_notified
    assert store.process_listings("s1", "S1", [lst], seeding=False)[0].kind == EventKind.NEW
    assert store.process_listings("s1", "S1", [lst], seeding=False)[0].kind == EventKind.NEW


def test_seeding_records_without_emitting(store):
    store.ensure_search("s1", "S1")
    lst = make_listing("m1")

    assert store.process_listings("s1", "S1", [lst], seeding=True) == []
    # later, not seeding: already known + notified -> still silent
    assert store.process_listings("s1", "S1", [lst], seeding=False) == []


def test_same_id_different_search_is_independent(store):
    store.ensure_search("s1", "S1")
    store.ensure_search("s2", "S2")
    lst = make_listing("shared")
    assert store.process_listings("s1", "S1", [lst], seeding=False)[0].kind == EventKind.NEW
    assert store.process_listings("s2", "S2", [lst], seeding=False)[0].kind == EventKind.NEW
