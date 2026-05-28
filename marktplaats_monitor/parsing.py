"""URL parsing, request-param assembly, and Dutch date/price helpers.

This module has two clearly separated parts:

* **Ours** — ``parse_search_url`` / ``_normalize_postcode`` /
  ``build_api_params`` / ``format_price``: translating a pasted Marktplaats
  URL + config into search-API parameters, and rendering prices.
* **Vendored** (clearly marked below, MIT-attributed) — the Dutch month map,
  the relative-date parser, the ``PriceType`` enum, and the condition-id map,
  adapted from **marktplaats-py**
  (https://github.com/jensjeflensje/marktplaats-py), ``src/marktplaats/``,
  v0.4.0, MIT License, Copyright (c) 2023 Jens de Ruiter. See
  ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, unquote, unquote_plus, urlsplit

logger = logging.getLogger(__name__)

DEFAULT_DISTANCE_KM = 50  # used when a postcode is given but no radius

# Fragment/query keys we understand (lower-cased). Anything else in a
# Marktplaats faceted-browse URL (category slugs, attribute facets like
# ``mileageFrom`` / ``constructionYearTo`` / numeric attribute ids) is not
# decodable here and is ignored rather than treated as an error.
_KNOWN_KEYS = {
    "q",
    "query",
    "postcode",
    "distancemeters",
    "pricefrom",
    "priceto",
    "pricecentsfrom",
    "pricecentsto",
    "l1categoryid",
    "l2categoryid",
    "sortby",
    "sortorder",
}
_CANONICAL = {
    "l1categoryid": "l1CategoryId",
    "l2categoryid": "l2CategoryId",
    "sortby": "sortBy",
    "sortorder": "sortOrder",
}

# ---------------------------------------------------------------------------
# VENDORED from marktplaats-py (MIT, (c) 2023 Jens de Ruiter) — adapted.
# Source: src/marktplaats/query.py, src/marktplaats/models/price_type.py
# Adaptation: parse_dutch_date returns None instead of raising on an unknown
# format, so a long-running monitor never crashes on a quirky date string.
# ---------------------------------------------------------------------------

_MONTH_MAPPING = {
    "jan": "Jan",
    "feb": "Feb",
    "mrt": "Mar",
    "apr": "Apr",
    "mei": "May",
    "jun": "Jun",
    "jul": "Jul",
    "aug": "Aug",
    "sep": "Sep",
    "okt": "Oct",
    "nov": "Nov",
    "dec": "Dec",
}


class PriceType(Enum):
    """Marktplaats ``priceInfo.priceType`` values."""

    FREE = "FREE"  # "Gratis"
    BID = "FAST_BID"  # "Bieden"
    RESERVED = "RESERVED"  # "Gereserveerd"
    SEE_DESCRIPTION = "SEE_DESCRIPTION"  # "Zie omschrijving"
    TO_BE_AGREED_UPON = "NOTK"  # "N.o.t.k."
    ON_REQUEST = "ON_REQUEST"  # "Op aanvraag"
    EXCHANGE = "EXCHANGE"  # "Ruilen"
    FIXED = "FIXED"  # a concrete price
    BID_FROM = "MIN_BID"  # asking price shown, bidding also possible
    UNKNOWN = "UNKNOWN"  # fallback for a type we don't know


# Condition attribute ids (from marktplaats-py's ``Condition`` enum).
CONDITION_IDS: dict[str, int] = {
    "new": 30,
    "as_good_as_new": 31,
    "used": 32,
    "refurbished": 14050,
    "not_working": 13940,
}


def parse_dutch_date(date_str: str | None) -> date | None:
    """Parse Marktplaats' Dutch date strings.

    Handles ``Vandaag`` / ``Gisteren`` / ``Eergisteren`` and ``"10 mrt 24"``.
    Returns ``None`` for anything unrecognised (rather than raising).
    """
    if not date_str:
        return None
    s = date_str.strip()
    if s == "Eergisteren":
        return (datetime.now() - timedelta(days=2)).date()
    if s == "Gisteren":
        return (datetime.now() - timedelta(days=1)).date()
    if s == "Vandaag":
        return datetime.now().date()
    converted = s
    for dutch, english in _MONTH_MAPPING.items():
        converted = converted.replace(dutch, english)
    try:
        return datetime.strptime(converted, "%d %b %y").date()
    except ValueError:
        return None


def condition_id(name: str | None) -> int | None:
    """Map a friendly condition name to its Marktplaats attribute id."""
    if not name:
        return None
    return CONDITION_IDS.get(name.strip().lower())


# ---------------------------------------------------------------------------
# OURS — URL parsing, price rendering, request-param assembly.
# ---------------------------------------------------------------------------

_PRICE_TYPE_LABELS_NL = {
    PriceType.FREE: "Gratis",
    PriceType.BID: "Bieden",
    PriceType.RESERVED: "Gereserveerd",
    PriceType.SEE_DESCRIPTION: "Zie omschrijving",
    PriceType.TO_BE_AGREED_UPON: "N.o.t.k.",
    PriceType.ON_REQUEST: "Op aanvraag",
    PriceType.EXCHANGE: "Ruilen",
    PriceType.BID_FROM: "Bieden vanaf",
}


@dataclass(frozen=True)
class PriceParts:
    """Rendered price: a human string, euros, cents, and the type.

    ``cents`` is only set for concrete prices (FIXED / BID_FROM); it is
    ``None`` for non-numeric types so price-drop logic ignores them.
    """

    display: str
    euros: float
    cents: int | None
    price_type: PriceType


def _euro(cents: int) -> str:
    return f"€ {cents // 100},{cents % 100:02d}"


def format_price(price_info: dict[str, Any] | None) -> PriceParts:
    """Map Marktplaats ``priceInfo`` to a :class:`PriceParts`."""
    info = price_info or {}
    raw_cents = info.get("priceCents")
    raw_type = info.get("priceType", "")
    try:
        price_type = PriceType(raw_type)
    except ValueError:
        price_type = PriceType.UNKNOWN

    if price_type in (PriceType.FIXED, PriceType.BID_FROM) and isinstance(raw_cents, int):
        euros = raw_cents / 100.0
        if price_type is PriceType.BID_FROM:
            return PriceParts(
                f"{_PRICE_TYPE_LABELS_NL[PriceType.BID_FROM]} {_euro(raw_cents)}",
                euros,
                raw_cents,
                price_type,
            )
        return PriceParts(_euro(raw_cents), euros, raw_cents, price_type)

    if price_type in _PRICE_TYPE_LABELS_NL:
        return PriceParts(_PRICE_TYPE_LABELS_NL[price_type], 0.0, None, price_type)

    if isinstance(raw_cents, int) and raw_cents > 0:
        # Unknown type but a real price is present — show it.
        return PriceParts(_euro(raw_cents), raw_cents / 100.0, raw_cents, price_type)

    return PriceParts("Prijs onbekend", 0.0, None, price_type)


def _normalize_postcode(postcode: str) -> str:
    """Normalize a Dutch postcode to ``1234 AB`` (Marktplaats accepts both)."""
    pc = postcode.upper().replace(" ", "")
    m = re.match(r"^(\d{4})([A-Z]{2})$", pc)
    return f"{m.group(1)} {m.group(2)}" if m else postcode.strip()


def parse_search_url(url: str, default_distance_km: int = DEFAULT_DISTANCE_KM) -> dict[str, Any]:
    """Parse a Marktplaats search URL into base search-API parameters.

    Understands the ``/q/<words>/`` path, ``?query=``/``?q=``, and the SPA
    filter fragment (``#q:auto|PriceCentsFrom:150000|distanceMeters:25000|
    postcode:1011AB``). Recognised fragment/query keys (case-insensitive):
    ``q``/``query``, ``postcode``, ``distanceMeters``,
    ``priceFrom``/``priceTo``, ``PriceCentsFrom``/``PriceCentsTo``,
    ``l1CategoryId``/``l2CategoryId``, ``sortBy``/``sortOrder``.

    Anything else in a faceted-browse URL (category/brand slugs in the path,
    attribute facets such as ``mileageFrom``/``constructionYearTo``, numeric
    attribute ids) cannot be decoded here. It is **ignored, not an error** —
    the search still runs on the parts we understand; ignored keys are logged
    at DEBUG so nothing is silently dropped without a trace.

    Returns a dict that may contain: ``query``, ``postcode``,
    ``distanceMeters``, ``price_min_cents``, ``price_max_cents``,
    ``l1CategoryId``, ``l2CategoryId``, ``sortBy``, ``sortOrder``.
    """
    parts = urlsplit(url)
    qs = parse_qs(parts.query)
    params: dict[str, Any] = {}

    # --- query: ?query / ?q / /q/<words>/ ---
    if "query" in qs:
        query = qs["query"][0]
    elif "q" in qs:
        query = qs["q"][0]
    else:
        m = re.search(r"/q/([^/]+)", parts.path)
        query = unquote_plus(m.group(1)).replace("+", " ") if m else ""
    params["query"] = query.strip()

    # --- pass-through filters from the query string ---
    for key in ("l1CategoryId", "l2CategoryId", "sortBy", "sortOrder"):
        if key in qs and qs[key][0]:
            params[key] = qs[key][0]

    qs_lower = {k.lower(): v[0] for k, v in qs.items() if v}
    price_min = _to_int(qs_lower.get("pricefrom") or qs_lower.get("pricecentsfrom"))
    price_max = _to_int(qs_lower.get("priceto") or qs_lower.get("pricecentsto"))

    postcode = qs_lower.get("postcode", "")
    distance_meters = _to_int(qs_lower.get("distancemeters"))

    # --- SPA fragment: key:value pairs joined by | or & ---
    if parts.fragment:
        ignored: list[str] = []
        for token in re.split(r"[|&]", unquote(parts.fragment)):
            key, _, value = token.partition(":")
            key, value = key.strip(), value.strip()
            if not key:
                continue
            lkey = key.lower()
            if not value:
                if lkey not in _KNOWN_KEYS:
                    ignored.append(key)
                continue
            if lkey in ("q", "query"):
                # The SPA carries the search term here; only fill it if the
                # path / query string didn't already give us one.
                if not params["query"]:
                    params["query"] = value.replace("+", " ").strip()
            elif lkey == "postcode":
                postcode = value
            elif lkey == "distancemeters":
                dm = _to_int(value)
                if dm is not None:
                    distance_meters = dm
            elif lkey in ("pricefrom", "pricecentsfrom"):
                price_min = _to_int(value)
            elif lkey in ("priceto", "pricecentsto"):
                price_max = _to_int(value)
            elif lkey in _CANONICAL:
                params[_CANONICAL[lkey]] = value
            else:
                ignored.append(key)
        if ignored:
            logger.debug(
                "Ignoring unsupported Marktplaats URL filters (not decodable, "
                "search still runs on the rest): %s",
                ", ".join(dict.fromkeys(ignored)),
            )

    if price_min is not None:
        params["price_min_cents"] = price_min
    if price_max is not None:
        params["price_max_cents"] = price_max

    if postcode:
        params["postcode"] = _normalize_postcode(postcode)
        # A postcode only filters together with a radius.
        params["distanceMeters"] = distance_meters or default_distance_km * 1000
    elif distance_meters is not None:
        params["distanceMeters"] = distance_meters

    return params


def build_base_params(
    *,
    url: str | None = None,
    query: str | None = None,
    postcode: str | None = None,
    distance_km: int = DEFAULT_DISTANCE_KM,
) -> dict[str, Any]:
    """Base params from **either** a pasted URL **or** a plain query.

    A search only needs one of: a Marktplaats ``url``, a ``query`` string, or
    a category (applied later). When both a URL and explicit config values are
    given, the explicit config wins (per-search config beats URL-embedded
    values) — this is also what finally makes a config-level ``postcode`` /
    ``distance_km`` take effect without crafting a URL.
    """
    base = parse_search_url(url, distance_km) if url else {"query": ""}
    if query:
        base["query"] = query.strip()
    if postcode:
        base["postcode"] = _normalize_postcode(postcode)
        base["distanceMeters"] = base.get("distanceMeters") or distance_km * 1000
    return base


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _price_cents_token(cents: int | None) -> str:
    # Marktplaats expects the literal string "null" for an open bound.
    return "null" if cents is None else str(cents)


def build_api_params(
    base: dict[str, Any],
    *,
    limit: int,
    offset: int,
    sort_by: str = "SORT_INDEX",
    sort_order: str = "DECREASING",
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    condition: str | None = None,
    offered_since: datetime | None = None,
    category_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble the final ``/lrp/api/search`` query params (pure function).

    ``base`` comes from :func:`parse_search_url`. Explicit keyword overrides
    (config) win over URL-derived values; ``None`` means "keep the URL value
    / built-in default".
    """
    params: dict[str, Any] = {
        "query": base.get("query", ""),
        "searchInTitleAndDescription": "true",
        "viewOptions": "list-view",
        "limit": int(limit),
        "offset": int(offset),
        "sortBy": base.get("sortBy") or sort_by,
        "sortOrder": base.get("sortOrder") or sort_order,
    }

    if base.get("postcode"):
        params["postcode"] = base["postcode"]
    if base.get("distanceMeters") is not None:
        params["distanceMeters"] = base["distanceMeters"]

    # Price: config override wins; otherwise fall back to the URL hints.
    pmin = price_min_cents if price_min_cents is not None else base.get("price_min_cents")
    pmax = price_max_cents if price_max_cents is not None else base.get("price_max_cents")
    if pmin is not None or pmax is not None:
        params["attributeRanges[]"] = [
            f"PriceCents:{_price_cents_token(pmin)}:{_price_cents_token(pmax)}"
        ]

    cid = condition_id(condition)
    if cid is not None:
        params["attributesById[]"] = [cid]

    if offered_since is not None:
        params["attributesByKey[]"] = [f"offeredSince:{int(offered_since.timestamp()) * 1000}"]

    # Category: explicit config category wins over a URL-embedded one.
    if category_params:
        params.update(category_params)
    else:
        for key in ("l1CategoryId", "l2CategoryId"):
            if base.get(key):
                params[key] = base[key]

    return params
