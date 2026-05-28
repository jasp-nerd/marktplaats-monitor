"""Seed /tmp/mp-demo.sqlite3 with realistic-looking data for the README demo.

Used by assets/demo.tape (VHS) so the `stats` command renders a populated
table instead of "No data yet." Not used at runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from marktplaats_monitor.state import StateStore

DB = "/tmp/mp-demo.sqlite3"
Path(DB).unlink(missing_ok=True)

store = StateStore(DB)
now = datetime.now(timezone.utc)
now_iso = now.isoformat()
old_iso = (now - timedelta(days=3)).isoformat()

# (search_id, display name, total_rows, last24h, avg_price_cents, new_alerts, drops)
SEARCHES = [
    ("apple-homepod", "Apple HomePod",            71,  6, 15647,  6, 0),
    ("alexa",         "Amazon Alexa",            187, 83, 10674, 20, 5),
    ("google-nest",   "Google Nest (speakers)",  108, 50,  8191, 21, 3),
]

for sid, name, total, last24h, avg_cents, new, drops in SEARCHES:
    store.conn.execute(
        "INSERT INTO searches(search_id, name, first_run_at, last_run_at) VALUES(?,?,?,?)",
        (sid, name, old_iso, now_iso),
    )
    for i in range(total):
        first = now_iso if i < last24h else old_iso
        store.conn.execute(
            "INSERT INTO listings(search_id, item_id, title, url, price_cents, "
            "last_price_cents, location, posted_raw, first_seen, last_seen, notified_new) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,1)",
            (sid, f"m{sid[:1]}{i:07d}", "demo listing", "https://demo",
             avg_cents, avg_cents, "Amsterdam", "Vandaag", first, first),
        )
    store.conn.execute(
        "INSERT INTO runs(search_id, run_at, fetched, passed_filter, new_count, drop_count) "
        "VALUES(?,?,?,?,?,?)",
        (sid, now_iso, total, total, new, drops),
    )

store.conn.commit()
store.close()
print(f"seeded {DB} with {sum(t for _, _, t, *_ in SEARCHES)} demo rows")
