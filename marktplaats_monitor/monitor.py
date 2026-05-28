"""Orchestrator: per-search pipeline + multi-search loop.

Pipeline per search per cycle:
  fetch → price/keyword filter → evaluator → state dedup/price-drop → notify

Notifications are sent *after* the state transaction; a listing is only
marked notified once its send succeeds (so a failed send retries next cycle).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from marktplaats_monitor.client import MarktplaatsClient
from marktplaats_monitor.config import Config, SearchConfig
from marktplaats_monitor.evaluator import ListingEvaluator, get_evaluator
from marktplaats_monitor.filters import ListingFilter
from marktplaats_monitor.models import EventKind, Listing, NotifyEvent, RunStats
from marktplaats_monitor.notify import Notifier
from marktplaats_monitor.notify.apprise_sink import AppriseSink
from marktplaats_monitor.state import StateStore

logger = logging.getLogger(__name__)


@dataclass
class _Runtime:
    search: SearchConfig
    client: MarktplaatsClient
    notifier: Notifier
    evaluator: ListingEvaluator
    filter: ListingFilter


def _build_runtime(search: SearchConfig) -> _Runtime:
    client = MarktplaatsClient(
        user_agent=search.http.user_agent,
        proxy=search.http.proxy,
        timeout=search.http.timeout,
        max_retries=search.http.max_retries,
        page_size=search.http.page_size,
        default_distance_km=search.distance_km,
        exclude_topblock=True,  # config: defaults.exclude_topblock (always true here)
        exclude_promoted=search.exclude_promoted,
    )
    sink = None
    if search.notify.apprise_urls:
        sink = AppriseSink(search.notify.apprise_url_specs())
    notifier = Notifier(
        apprise_sink=sink,
        discord_webhook=search.notify.discord_webhook,
        listings_tag=search.notify.tags.get("listings", ["listings"]),
        errors_tag=search.notify.tags.get("errors", ["errors"]),
    )
    return _Runtime(
        search=search,
        client=client,
        notifier=notifier,
        evaluator=get_evaluator(search.evaluator.type, search.evaluator.options),
        filter=search.listing_filter(),
    )


class Monitor:
    """Owns the state store and per-search runtimes."""

    def __init__(self, config: Config, store: StateStore) -> None:
        self.config = config
        self.store = store
        self.runtimes = [_build_runtime(s) for s in config.searches]

    # -- one search cycle --------------------------------------------------

    def run_search(self, rt: _Runtime) -> RunStats:
        s = rt.search
        stats = RunStats(search_id=s.id)
        seeding = self.store.ensure_search(s.id, s.name)
        try:
            offered_since = None
            if s.offered_since_minutes:
                offered_since = datetime.now() - timedelta(minutes=s.offered_since_minutes)

            listings = rt.client.search(
                s.url,
                query=s.query,
                postcode=s.postcode,
                max_pages=s.max_pages,
                price_min_cents=s.price_min_cents,
                price_max_cents=s.price_max_cents,
                condition=s.condition,
                offered_since=offered_since,
                category_params=s.category_params,
            )
            stats.fetched = len(listings)

            kept: list[Listing] = []
            evals: dict[str, tuple[float | None, str | None]] = {}
            for lst in listings:
                if not rt.filter.passes(lst):
                    continue
                ev = rt.evaluator.evaluate(lst, s)
                if not ev.keep:
                    continue
                kept.append(lst)
                if ev.score is not None or ev.label is not None:
                    evals[lst.item_id] = (ev.score, ev.label)
            stats.passed_filter = len(kept)

            events = self.store.process_listings(s.id, s.name, kept, seeding=seeding)
            for item_id, (score, label) in evals.items():
                self.store.set_evaluation(s.id, item_id, score, label)

            for ev in events:
                self._dispatch(rt, ev, stats)

            self.store.mark_run_complete(s.id)
            if seeding:
                logger.info("[%s] seeded %d listings (no alerts)", s.id, stats.passed_filter)
            else:
                logger.info(
                    "[%s] fetched=%d kept=%d new=%d drops=%d",
                    s.id,
                    stats.fetched,
                    stats.passed_filter,
                    stats.new_count,
                    stats.drop_count,
                )
        except Exception as e:  # noqa: BLE001 — one search must not kill the loop
            stats.error = str(e)
            logger.error("[%s] cycle failed: %s", s.id, e)
        self.store.record_run(stats)
        return stats

    def _dispatch(self, rt: _Runtime, event: NotifyEvent, stats: RunStats) -> None:
        ok = rt.notifier.send_event(
            event,
            backend=rt.search.notify.backend,
            mention=rt.search.notify.mention,
            attach_image=rt.search.notify.attach_image,
        )
        if not ok:
            stats.notify_failures.append(event.listing.item_id)
            logger.warning(
                "[%s] notify failed for %s — will retry next cycle",
                rt.search.id,
                event.listing.item_id,
            )
            return
        if event.kind is EventKind.NEW:
            self.store.mark_new_notified(event.search_id, event.listing.item_id)
            stats.new_count += 1
        else:
            self.store.mark_drop_notified(
                event.search_id, event.listing.item_id, event.new_price_cents
            )
            stats.drop_count += 1

    # -- entry points ------------------------------------------------------

    def run_once(self) -> int:
        any_error = False
        for rt in self.runtimes:
            stats = self.run_search(rt)
            any_error = any_error or bool(stats.error)
        return 1 if any_error else 0

    def run_forever(self, interval: int, max_consecutive_failures: int = 5) -> int:
        logger.info(
            "Monitoring %d search(es) every %ds. Ctrl-C to stop.",
            len(self.runtimes),
            interval,
        )
        consecutive = 0
        try:
            while True:
                start = time.monotonic()
                cycle_failed = False
                for rt in self.runtimes:
                    if self.run_search(rt).error:
                        cycle_failed = True
                consecutive = consecutive + 1 if cycle_failed else 0
                if consecutive >= max_consecutive_failures:
                    logger.error("Stopping: %d consecutive failed cycles", consecutive)
                    return 1
                sleep_for = max(5, interval - int(time.monotonic() - start))
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            return 0

    def send_test(self) -> int:
        """Send one synthetic notification per search through its backend."""
        from marktplaats_monitor.parsing import PriceParts, PriceType

        ok_all = True
        for rt in self.runtimes:
            sample = Listing(
                item_id="test-0000",
                title="✅ Test listing — Marktplaats Monitor",
                description="If you can read this, notifications work.",
                url="https://www.marktplaats.nl/",
                price=PriceParts("€ 42,00", 42.0, 4200, PriceType.FIXED),
                location="Amsterdam",
                country="Nederland",
                distance_meters=1234,
                seller_name="Monitor",
                seller_verified=True,
                posted_raw="Vandaag",
                posted_at=None,
                image_url="",
                condition="Nieuw",
                category_id=None,
            )
            event = NotifyEvent(EventKind.NEW, sample, rt.search.id, rt.search.name)
            ok = rt.notifier.send_event(
                event,
                backend=rt.search.notify.backend,
                mention=rt.search.notify.mention,
                attach_image=False,
            )
            status = "OK" if ok else "FAILED"
            logger.info("[%s] test notification: %s", rt.search.id, status)
            ok_all = ok_all and ok
        return 0 if ok_all else 1

    def close(self) -> None:
        for rt in self.runtimes:
            rt.client.close()
