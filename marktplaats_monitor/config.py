"""YAML config loading, secret resolution, merging and validation.

Layout: a ``defaults:`` block and a ``searches:`` list. Each search inherits
``defaults`` and may override any of the per-search keys. Secrets never live
in the YAML — reference them with an ``env:NAME`` token (resolved from the
environment / ``.env`` after ``load_dotenv()``).

Precedence (high → low): CLI flag → env → per-search → defaults → built-in.
CLI overrides are applied by the caller (see ``cli.py``); this module handles
env/per-search/defaults/built-in.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from marktplaats_monitor.categories import category_api_params, resolve_category
from marktplaats_monitor.evaluator import available_evaluators
from marktplaats_monitor.filters import ListingFilter
from marktplaats_monitor.parsing import CONDITION_IDS

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_VALID_BACKENDS = {"apprise", "discord_native"}
_VALID_MENTION = re.compile(r"^(none|everyone|here|role:.+)$")


class ConfigError(Exception):
    """Raised for any invalid configuration (message is user-facing)."""


# -- resolved dataclasses ---------------------------------------------------


@dataclass
class HttpConfig:
    user_agent: str | None = None
    proxy: str | None = None
    timeout: int = 15
    max_retries: int = 3
    page_size: int = 100


@dataclass
class NotifyConfig:
    backend: str = "apprise"
    apprise_urls: list[str] = field(default_factory=list)
    discord_webhook: str | None = None
    tags: dict[str, list[str]] = field(
        default_factory=lambda: {"listings": ["listings"], "errors": ["errors"]}
    )
    attach_image: bool = True
    mention: str = "none"

    def apprise_url_specs(self) -> list[tuple[str, list[str]]]:
        """(url, tags) pairs; listing alerts and errors share every URL but
        are tagged so a user *could* route them differently."""
        all_tags = sorted({t for ts in self.tags.values() for t in ts})
        return [(u, all_tags) for u in self.apprise_urls if u]


@dataclass
class EvaluatorConfig:
    type: str = "noop"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchConfig:
    id: str
    name: str
    url: str | None = None
    query: str | None = None
    price_min_cents: int | None = None
    price_max_cents: int | None = None
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    distance_km: int = 50
    postcode: str | None = None
    condition: str | None = None
    category_name: str | None = None
    category_params: dict[str, str] | None = None
    max_pages: int = 1
    poll_interval: int | None = None
    offered_since_minutes: int | None = None
    seed_without_notify: bool = True
    exclude_promoted: bool = True
    http: HttpConfig = field(default_factory=HttpConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    evaluator: EvaluatorConfig = field(default_factory=EvaluatorConfig)

    def listing_filter(self) -> ListingFilter:
        return ListingFilter.build(
            price_min_cents=self.price_min_cents,
            price_max_cents=self.price_max_cents,
            include_keywords=self.include_keywords,
            exclude_keywords=self.exclude_keywords,
        )


@dataclass
class Config:
    check_interval: int
    searches: list[SearchConfig]


# -- loading ----------------------------------------------------------------


def _resolve_secret(value: Any, ref: str, missing: list[str]) -> Any:
    """Replace an ``env:NAME`` token with the environment value."""
    if isinstance(value, str) and value.startswith("env:"):
        name = value[4:]
        env_val = os.environ.get(name)
        if env_val is None or env_val == "":
            missing.append(f"{name} (referenced by {ref})")
            return None
        return env_val
    if isinstance(value, list):
        return [_resolve_secret(v, ref, missing) for v in value]
    return value


def _euros_to_cents(v: Any) -> int | None:
    if v is None:
        return None
    return int(round(float(v) * 100))


def _merge(defaults: dict, override: dict) -> dict:
    """Shallow merge with one nested level for ``notify``/``evaluator``."""
    out = dict(defaults)
    for k, v in override.items():
        if k in ("notify", "evaluator") and isinstance(v, dict):
            out[k] = {**defaults.get(k, {}), **v}
        else:
            out[k] = v
    return out


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("Top-level config must be a mapping with 'searches:'")

    defaults = raw.get("defaults") or {}
    searches_raw = raw.get("searches") or []
    if not searches_raw:
        raise ConfigError("No searches configured (the 'searches:' list is empty)")

    missing: list[str] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    searches: list[SearchConfig] = []

    for i, s in enumerate(searches_raw):
        if not isinstance(s, dict):
            errors.append(f"searches[{i}] must be a mapping")
            continue
        merged = _merge(defaults, s)
        sid = str(merged.get("id", "")).strip()
        ref = f"search '{sid or i}'"

        if not sid or not _ID_RE.match(sid):
            errors.append(f"searches[{i}]: invalid or missing id {sid!r} (use [a-z0-9_-])")
        elif sid in seen_ids:
            errors.append(f"duplicate search id: {sid}")
        seen_ids.add(sid)

        if not (merged.get("url") or merged.get("query") or merged.get("category")):
            errors.append(f"{ref}: needs at least one of 'url', 'query', or 'category'")

        pmin = _euros_to_cents(merged.get("price_min"))
        pmax = _euros_to_cents(merged.get("price_max"))
        if pmin is not None and pmax is not None and pmin > pmax:
            errors.append(
                f"{ref}: price_min ({merged['price_min']}) > price_max ({merged['price_max']})"
            )

        condition = merged.get("condition")
        if condition and condition.lower() not in CONDITION_IDS:
            errors.append(f"{ref}: unknown condition {condition!r}; valid: {sorted(CONDITION_IDS)}")

        pi = merged.get("poll_interval")
        if pi is not None:
            try:
                if int(pi) < 1:
                    errors.append(f"{ref}: poll_interval must be >= 1 second")
                elif int(pi) < 5:
                    logger.warning(
                        "%s: poll_interval=%ss is below the 5s minimum — it will run at 5s", ref, pi
                    )
            except (TypeError, ValueError):
                errors.append(f"{ref}: poll_interval must be an integer number of seconds")

        category_name = merged.get("category")
        category_params = None
        if category_name:
            cat = resolve_category(category_name)
            if cat is None:
                logger.warning(
                    "%s: unknown category %r — ignoring category filter", ref, category_name
                )
                category_name = None
            else:
                category_params = category_api_params(cat)

        nraw = merged.get("notify") or {}
        notify = NotifyConfig(
            backend=nraw.get("backend", "apprise"),
            apprise_urls=[
                u
                for u in _resolve_secret(
                    nraw.get("apprise_urls", []), f"{ref} notify.apprise_urls", missing
                )
                if u
            ],
            discord_webhook=_resolve_secret(
                nraw.get("discord_webhook"), f"{ref} notify.discord_webhook", missing
            ),
            tags=nraw.get("tags") or {"listings": ["listings"], "errors": ["errors"]},
            attach_image=bool(nraw.get("attach_image", True)),
            mention=str(nraw.get("mention", "none")),
        )
        if notify.backend not in _VALID_BACKENDS:
            errors.append(f"{ref}: notify.backend must be one of {sorted(_VALID_BACKENDS)}")
        if not _VALID_MENTION.match(notify.mention):
            errors.append(f"{ref}: notify.mention must be none|everyone|here|role:<id>")
        if notify.backend == "discord_native" and not notify.discord_webhook:
            errors.append(f"{ref}: notify.backend is discord_native but no discord_webhook set")
        if notify.backend == "apprise" and not notify.apprise_urls and not missing:
            logger.warning("%s: apprise backend but no apprise_urls — alerts won't send", ref)

        eraw = merged.get("evaluator") or {}
        evaluator = EvaluatorConfig(
            type=eraw.get("type", "noop"), options=eraw.get("options") or {}
        )
        if evaluator.type not in available_evaluators():
            errors.append(
                f"{ref}: unknown evaluator.type {evaluator.type!r}; "
                f"available: {available_evaluators()}"
            )

        hraw = merged.get("http") or {}
        http = HttpConfig(
            user_agent=hraw.get("user_agent"),
            proxy=_resolve_secret(hraw.get("proxy"), f"{ref} http.proxy", missing),
            timeout=int(hraw.get("timeout", 15)),
            max_retries=int(hraw.get("max_retries", 3)),
            page_size=int(hraw.get("page_size", 100)),
        )

        # validate exclude regexes early (raises re.error -> ConfigError)
        try:
            ListingFilter.build(exclude_keywords=merged.get("exclude_keywords") or [])
        except re.error as e:
            errors.append(f"{ref}: {e}")

        searches.append(
            SearchConfig(
                id=sid,
                name=str(merged.get("name") or sid),
                url=(str(merged["url"]).strip() if merged.get("url") else None),
                query=(str(merged["query"]).strip() if merged.get("query") else None),
                price_min_cents=pmin,
                price_max_cents=pmax,
                include_keywords=list(merged.get("include_keywords") or []),
                exclude_keywords=list(merged.get("exclude_keywords") or []),
                distance_km=int(merged.get("distance_km", 50)),
                postcode=merged.get("postcode"),
                condition=condition.lower() if condition else None,
                category_name=category_name,
                category_params=category_params,
                max_pages=int(merged.get("max_pages", 1)),
                poll_interval=(
                    int(merged["poll_interval"]) if merged.get("poll_interval") else None
                ),
                offered_since_minutes=merged.get("offered_since_minutes"),
                seed_without_notify=bool(merged.get("seed_without_notify", True)),
                exclude_promoted=bool(merged.get("exclude_promoted", True)),
                http=http,
                notify=notify,
                evaluator=evaluator,
            )
        )

    if missing:
        raise ConfigError(
            "Missing required environment variable(s):\n  - " + "\n  - ".join(sorted(set(missing)))
        )
    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return Config(
        check_interval=int(defaults.get("check_interval", 60)),
        searches=searches,
    )
