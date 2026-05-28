import pytest

from marktplaats_monitor.models import RunStats
from marktplaats_monitor.state import StateStore
from tests.conftest import make_listing


@pytest.fixture
def store(tmp_path):
    s = StateStore(tmp_path / "state.sqlite3")
    yield s
    s.close()


def test_stats_summary_aggregates(store):
    store.ensure_search("s1", "Bikes")
    store.process_listings(
        "s1",
        "Bikes",
        [make_listing("m1", cents=10000), make_listing("m2", cents=30000)],
        seeding=False,
    )
    store.record_run(
        RunStats(search_id="s1", fetched=2, passed_filter=2, new_count=2, drop_count=0)
    )
    store.mark_run_complete("s1")

    summary = store.stats_summary()
    assert len(summary) == 1
    row = summary[0]
    assert row["search_id"] == "s1"
    assert row["total_listings"] == 2
    assert row["listings_last_24h"] == 2
    assert row["avg_price_eur"] == 200.0  # (100 + 300) / 2
    assert row["new_total"] == 2
    assert row["last_run_at"] is not None


def test_schema_version_recorded(store):
    row = store.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert row["value"] == "1"
