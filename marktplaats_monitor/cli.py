"""Command-line interface: ``run`` | ``once`` | ``test`` | ``stats``.

python -m marktplaats_monitor run        # daemon (poll forever)
python -m marktplaats_monitor once       # one full cycle, then exit
python -m marktplaats_monitor test       # send a sample notification
python -m marktplaats_monitor stats      # print per-search statistics
"""

from __future__ import annotations

import argparse
import logging
import os

DEFAULT_CONFIG = os.environ.get("CONFIG_FILE", "config.yaml")
DEFAULT_DB = os.environ.get("DB_PATH", "data/monitor.sqlite3")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="marktplaats-monitor", description=__doc__)
    p.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG, help=f"YAML config (default: {DEFAULT_CONFIG})"
    )
    p.add_argument("--db", default=DEFAULT_DB, help=f"SQLite state file (default: {DEFAULT_DB})")
    p.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="DEBUG | INFO | WARNING | ERROR",
    )
    p.add_argument(
        "command",
        choices=["run", "once", "test", "stats"],
        help="what to do",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _setup_logging(args.log_level)
    log = logging.getLogger("marktplaats_monitor")

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover
        log.warning("python-dotenv not installed; using process environment only")

    from marktplaats_monitor.state import StateStore

    # `stats` only needs the DB, not a valid config.
    if args.command == "stats":
        store = StateStore(args.db)
        try:
            _print_stats(store.stats_summary())
        finally:
            store.close()
        return 0

    from marktplaats_monitor.config import ConfigError, load_config

    try:
        config = load_config(args.config)
    except ConfigError as e:
        log.error("Configuration error:\n%s", e)
        return 2

    from marktplaats_monitor.monitor import Monitor

    store = StateStore(args.db)
    monitor = Monitor(config, store)
    try:
        if args.command == "once":
            return monitor.run_once()
        if args.command == "test":
            return monitor.send_test()
        return monitor.run_forever(config.check_interval)
    finally:
        monitor.close()
        store.close()


def _print_stats(rows: list[dict]) -> None:
    if not rows:
        print("No data yet. Run the monitor first.")
        return
    print(f"{'SEARCH':<22} {'TOTAL':>6} {'24H':>5} {'AVG €':>9} {'NEW':>5} {'DROPS':>6}  LAST RUN")
    print("-" * 80)
    for r in rows:
        avg = f"{r['avg_price_eur']:.2f}" if r["avg_price_eur"] is not None else "-"
        print(
            f"{r['name'][:22]:<22} {r['total_listings']:>6} {r['listings_last_24h']:>5} "
            f"{avg:>9} {r['new_total']:>5} {r['drop_total']:>6}  {r['last_run_at'] or '-'}"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
