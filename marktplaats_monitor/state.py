"""SQLite state store: dedup, price-drop detection, and stats.

One DB file (Docker-volume friendly). Dedup is keyed on the stable
Marktplaats ``itemId`` so a price/title edit does not fire a false "new".

Notify-retry safety:
* A **new** listing is inserted with ``notified_new=0`` and only flipped to
  ``1`` once the notification actually sends (:meth:`mark_new_notified`). If a
  send fails it is re-emitted next cycle. Seeded listings are inserted with
  ``notified_new=1`` so they never alert.
* A **price drop** is emitted when the price falls below both the previously
  stored price and any price we already alerted for. ``notified_drop_at_cents``
  is set on send success. Drop alerts are best-effort (documented).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from marktplaats_monitor.models import EventKind, Listing, NotifyEvent, RunStats

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS searches (
  search_id    TEXT PRIMARY KEY,
  name         TEXT,
  first_run_at TEXT,
  last_run_at  TEXT
);

CREATE TABLE IF NOT EXISTS listings (
  search_id              TEXT NOT NULL,
  item_id                TEXT NOT NULL,
  title                  TEXT,
  url                    TEXT,
  price_cents            INTEGER,
  last_price_cents       INTEGER,
  location               TEXT,
  posted_raw             TEXT,
  posted_at              TEXT,
  first_seen             TEXT NOT NULL,
  last_seen              TEXT NOT NULL,
  notified_new           INTEGER NOT NULL DEFAULT 0,
  notified_drop_at_cents INTEGER,
  evaluator_score        REAL,
  evaluator_label        TEXT,
  PRIMARY KEY (search_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_search ON listings(search_id);
CREATE INDEX IF NOT EXISTS idx_listings_firstseen ON listings(first_seen);

CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  search_id     TEXT NOT NULL,
  run_at        TEXT NOT NULL,
  fetched       INTEGER,
  passed_filter INTEGER,
  new_count     INTEGER,
  drop_count    INTEGER,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_search_time ON runs(search_id, run_at);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class StateStore:
    """Thin repository around a SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = str(db_path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(_SCHEMA)
        self.conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self.conn.commit()

    # -- searches ----------------------------------------------------------

    def ensure_search(self, search_id: str, name: str) -> bool:
        """Register a search; return True if it is still **seeding**."""
        self.conn.execute(
            "INSERT INTO searches(search_id, name) VALUES(?, ?) "
            "ON CONFLICT(search_id) DO UPDATE SET name=excluded.name",
            (search_id, name),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT first_run_at FROM searches WHERE search_id=?", (search_id,)
        ).fetchone()
        return row["first_run_at"] is None

    def mark_run_complete(self, search_id: str) -> None:
        now = _utcnow()
        self.conn.execute(
            "UPDATE searches SET last_run_at=?, "
            "first_run_at=COALESCE(first_run_at, ?) WHERE search_id=?",
            (now, now, search_id),
        )
        self.conn.commit()

    # -- dedup / price-drop ------------------------------------------------

    def process_listings(
        self,
        search_id: str,
        search_name: str,
        listings: list[Listing],
        *,
        seeding: bool,
    ) -> list[NotifyEvent]:
        """Upsert a cycle's listings in one transaction; return events."""
        events: list[NotifyEvent] = []
        now = _utcnow()
        with self.conn:  # atomic commit / rollback
            for lst in listings:
                events.extend(self._upsert(search_id, search_name, lst, now, seeding))
        return events

    def _upsert(
        self,
        search_id: str,
        search_name: str,
        lst: Listing,
        now: str,
        seeding: bool,
    ) -> list[NotifyEvent]:
        row = self.conn.execute(
            "SELECT * FROM listings WHERE search_id=? AND item_id=?",
            (search_id, lst.item_id),
        ).fetchone()
        new_cents = lst.price_cents

        if row is None:
            self.conn.execute(
                "INSERT INTO listings(search_id, item_id, title, url, price_cents, "
                "last_price_cents, location, posted_raw, posted_at, first_seen, "
                "last_seen, notified_new) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    search_id,
                    lst.item_id,
                    lst.title,
                    lst.url,
                    new_cents,
                    new_cents,
                    lst.location,
                    lst.posted_raw,
                    lst.posted_at.isoformat() if lst.posted_at else None,
                    now,
                    now,
                    1 if seeding else 0,
                ),
            )
            if seeding:
                return []
            return [self._event(EventKind.NEW, lst, search_id, search_name)]

        old_cents = row["price_cents"]
        self.conn.execute(
            "UPDATE listings SET last_seen=?, title=?, url=?, location=?, "
            "last_price_cents=?, price_cents=? WHERE search_id=? AND item_id=?",
            (
                now,
                lst.title,
                lst.url,
                lst.location,
                old_cents,
                new_cents,
                search_id,
                lst.item_id,
            ),
        )

        # Pending NEW (a previous send failed) takes priority over drops.
        if not row["notified_new"] and not seeding:
            return [self._event(EventKind.NEW, lst, search_id, search_name)]

        if isinstance(new_cents, int) and isinstance(old_cents, int) and new_cents < old_cents:
            floor = row["notified_drop_at_cents"]
            if floor is None or new_cents < floor:
                return [
                    self._event(
                        EventKind.PRICE_DROP,
                        lst,
                        search_id,
                        search_name,
                        old_cents=old_cents,
                        new_cents=new_cents,
                    )
                ]
        return []

    @staticmethod
    def _event(
        kind: EventKind,
        lst: Listing,
        search_id: str,
        search_name: str,
        *,
        old_cents: int | None = None,
        new_cents: int | None = None,
    ) -> NotifyEvent:
        return NotifyEvent(
            kind=kind,
            listing=lst,
            search_id=search_id,
            search_name=search_name,
            old_price_cents=old_cents,
            new_price_cents=new_cents,
        )

    # -- notify bookkeeping (called after a successful send) ---------------

    def mark_new_notified(self, search_id: str, item_id: str) -> None:
        self.conn.execute(
            "UPDATE listings SET notified_new=1 WHERE search_id=? AND item_id=?",
            (search_id, item_id),
        )
        self.conn.commit()

    def mark_drop_notified(self, search_id: str, item_id: str, price_cents: int) -> None:
        self.conn.execute(
            "UPDATE listings SET notified_drop_at_cents=? " "WHERE search_id=? AND item_id=?",
            (price_cents, search_id, item_id),
        )
        self.conn.commit()

    def set_evaluation(
        self,
        search_id: str,
        item_id: str,
        score: float | None,
        label: str | None,
    ) -> None:
        self.conn.execute(
            "UPDATE listings SET evaluator_score=?, evaluator_label=? "
            "WHERE search_id=? AND item_id=?",
            (score, label, search_id, item_id),
        )
        self.conn.commit()

    # -- runs / stats ------------------------------------------------------

    def record_run(self, stats: RunStats) -> None:
        self.conn.execute(
            "INSERT INTO runs(search_id, run_at, fetched, passed_filter, "
            "new_count, drop_count, error) VALUES(?,?,?,?,?,?,?)",
            (
                stats.search_id,
                _utcnow(),
                stats.fetched,
                stats.passed_filter,
                stats.new_count,
                stats.drop_count,
                stats.error,
            ),
        )
        self.conn.commit()

    def stats_summary(self) -> list[dict]:
        cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        rows = self.conn.execute("SELECT search_id, name, last_run_at FROM searches").fetchall()
        out = []
        for s in rows:
            sid = s["search_id"]
            agg = self.conn.execute(
                "SELECT COUNT(*) AS total, "
                "AVG(price_cents) AS avg_cents, "
                "SUM(CASE WHEN first_seen >= ? THEN 1 ELSE 0 END) AS last24h "
                "FROM listings WHERE search_id=?",
                (cutoff, sid),
            ).fetchone()
            runs = self.conn.execute(
                "SELECT COALESCE(SUM(new_count),0) AS new_total, "
                "COALESCE(SUM(drop_count),0) AS drop_total FROM runs WHERE search_id=?",
                (sid,),
            ).fetchone()
            out.append(
                {
                    "search_id": sid,
                    "name": s["name"],
                    "last_run_at": s["last_run_at"],
                    "total_listings": agg["total"],
                    "listings_last_24h": agg["last24h"],
                    "avg_price_eur": round(agg["avg_cents"] / 100, 2) if agg["avg_cents"] else None,
                    "new_total": runs["new_total"],
                    "drop_total": runs["drop_total"],
                }
            )
        return out

    def close(self) -> None:
        self.conn.close()
