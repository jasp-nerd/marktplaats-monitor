"""Our own thin Marktplaats search-API client.

Owning the HTTP layer (session, headers, retry/backoff, optional proxy) is a
deliberate choice: this is a 24/7 poller and we need control a generic
library doesn't expose. Listing parsing is grounded in ``docs/marktplaats-api.md``.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Any

import requests

from marktplaats_monitor.models import Listing
from marktplaats_monitor.parsing import (
    build_api_params,
    build_base_params,
    format_price,
    parse_dutch_date,
)

logger = logging.getLogger(__name__)

API_URL = "https://www.marktplaats.nl/lrp/api/search"
BASE_URL = "https://www.marktplaats.nl"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MISSING_DISTANCE = -1000  # API sentinel for "unknown distance"

# `priorityProduct` values that mark a *paid promotion* (vs the normal
# "NONE"). These are floated to the top of results and refresh daily, so for
# a new-listing monitor they are stable noise — dropped when exclude_promoted.
_PROMOTED_PRIORITY = {"DAGTOPPER", "TOPADVERTENTIE"}


class MarktplaatsClient:
    """Fetches and normalizes Marktplaats listings."""

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: int = 15,
        max_retries: int = 3,
        page_size: int = 100,
        default_distance_km: int = 50,
        exclude_topblock: bool = True,
        exclude_promoted: bool = True,
        backoff_base: float = 1.0,
        backoff_cap: float = 60.0,
        page_pause: float = 1.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = max(1, min(page_size, 100))
        self.default_distance_km = default_distance_km
        self.exclude_topblock = exclude_topblock
        self.exclude_promoted = exclude_promoted
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.page_pause = page_pause

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent
                or (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Referer": BASE_URL + "/",
            }
        )
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    # -- HTTP with retry/backoff -------------------------------------------

    def _sleep_for(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap)
            except ValueError:
                pass
        return min(self.backoff_cap, self.backoff_base * (2**attempt)) + random.uniform(0, 1)

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET the search API with bounded exponential backoff + jitter."""
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(API_URL, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                last_err = e
                logger.warning("API request error (attempt %d): %s", attempt + 1, e)
            else:
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code not in _RETRYABLE_STATUS:
                    resp.raise_for_status()
                    raise RuntimeError(f"Unexpected status {resp.status_code}")
                last_err = RuntimeError(f"HTTP {resp.status_code}")
                if attempt < self.max_retries:
                    delay = self._sleep_for(attempt, resp.headers.get("Retry-After"))
                    logger.warning(
                        "API HTTP %s (attempt %d), retrying in %.1fs",
                        resp.status_code,
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                continue

            if attempt < self.max_retries:
                delay = self._sleep_for(attempt, None)
                time.sleep(delay)

        raise RuntimeError(
            f"Marktplaats API failed after {self.max_retries + 1} attempts"
        ) from last_err

    # -- public API --------------------------------------------------------

    def search(
        self,
        search_url: str | None = None,
        *,
        query: str | None = None,
        postcode: str | None = None,
        max_pages: int = 1,
        sort_by: str = "SORT_INDEX",
        sort_order: str = "DECREASING",
        price_min_cents: int | None = None,
        price_max_cents: int | None = None,
        condition: str | None = None,
        offered_since: datetime | None = None,
        category_params: dict[str, str] | None = None,
    ) -> list[Listing]:
        """Fetch and normalize listings for a pasted URL or a plain query.

        Default sort is ``SORT_INDEX/DECREASING`` — Marktplaats' own
        "Nieuwste eerst" sort, which delivers strict chronological order
        (newest first) for any reasonably narrow query. Combined with
        ``exclude_promoted`` (default true) the few DAGTOPPER paid promos
        that float to the top are filtered, leaving pure date-ordered
        organic listings. ``OPTIMIZED/DECREASING`` is the site's *relevance*
        sort and produces hundreds of date-inversions, so it is wrong for
        a new-listing monitor.

        Known limitation: for *ultra-broad* queries (e.g. a single common
        word with 100k+ results) the DAGTOPPER pool is large enough to
        fill page 1 entirely; after ``exclude_promoted`` filters them you
        get an empty page. Narrow the query (category, price, postcode) or
        disable ``exclude_promoted``.
        """
        base = build_base_params(
            url=search_url,
            query=query,
            postcode=postcode,
            distance_km=self.default_distance_km,
        )
        if not base.get("query") and not (category_params or base.get("l1CategoryId")):
            logger.warning("Search has no query, URL query, or category — results unfiltered")

        results: list[Listing] = []
        seen: set[str] = set()

        for page in range(max_pages):
            params = build_api_params(
                base,
                limit=self.page_size,
                offset=page * self.page_size,
                sort_by=sort_by,
                sort_order=sort_order,
                price_min_cents=price_min_cents,
                price_max_cents=price_max_cents,
                condition=condition,
                offered_since=offered_since,
                category_params=category_params,
            )
            data = self._get(params)

            organic = data.get("listings") or []
            sponsored = [] if self.exclude_topblock else (data.get("topBlock") or [])
            page_count = 0
            for raw, is_sponsored in [(i, False) for i in organic] + [(i, True) for i in sponsored]:
                item_id = raw.get("itemId")
                if not item_id or item_id in seen:
                    continue
                if (
                    self.exclude_promoted
                    and not is_sponsored
                    and raw.get("priorityProduct") in _PROMOTED_PRIORITY
                ):
                    continue
                seen.add(item_id)
                listing = self._to_listing(raw, is_sponsored)
                if listing is not None:
                    results.append(listing)
                    page_count += 1

            total = data.get("totalResultCount", 0)
            logger.info(
                "page %d/%d: +%d listings (total so far %d)",
                page + 1,
                max_pages,
                page_count,
                len(results),
            )
            if not organic or (page + 1) * self.page_size >= total:
                break
            if page + 1 < max_pages:
                time.sleep(self.page_pause)

        return results

    # -- parsing -----------------------------------------------------------

    @staticmethod
    def _image_url(raw: dict[str, Any]) -> str:
        pics = raw.get("pictures") or []
        if pics:
            first = pics[0]
            for key in ("largeUrl", "extraExtraLargeUrl", "mediumUrl", "extraSmallUrl"):
                val = first.get(key)
                if val and "#" not in val:
                    return val
        for img in raw.get("imageUrls") or []:
            if img:
                return "https:" + img if img.startswith("//") else img
        return ""

    def _to_listing(self, raw: dict[str, Any], is_sponsored: bool) -> Listing | None:
        try:
            title = (raw.get("title") or "").strip()
            item_id = raw.get("itemId")
            if not title or not item_id:
                return None

            price = format_price(raw.get("priceInfo"))

            loc = raw.get("location") or {}
            city = loc.get("cityName") or loc.get("countryName") or "Locatie onbekend"
            distance = loc.get("distanceMeters")
            if distance == _MISSING_DISTANCE or distance is None:
                distance = None

            seller = raw.get("sellerInformation") or {}

            desc = (raw.get("categorySpecificDescription") or raw.get("description") or "").strip()
            if len(desc) > 500:
                desc = desc[:497] + "..."

            vip = raw.get("vipUrl") or ""
            if vip.startswith("/"):
                url = BASE_URL + vip
            elif vip.startswith("http"):
                url = vip
            else:
                url = f"https://link.marktplaats.nl/{item_id}"

            condition = ""
            for attr in raw.get("attributes") or []:
                if attr.get("key") == "condition" and attr.get("value"):
                    condition = str(attr["value"])
                    break

            return Listing(
                item_id=str(item_id),
                title=title,
                description=desc,
                url=url,
                price=price,
                location=city,
                country=loc.get("countryName") or "",
                distance_meters=distance,
                seller_name=seller.get("sellerName") or "",
                seller_verified=bool(seller.get("isVerified")),
                posted_raw=raw.get("date") or "",
                posted_at=parse_dutch_date(raw.get("date")),
                image_url=self._image_url(raw),
                condition=condition,
                category_id=raw.get("categoryId"),
                is_sponsored=is_sponsored,
            )
        except Exception as e:  # noqa: BLE001 — never let one bad listing crash a cycle
            logger.error("Failed to parse listing %s: %s", raw.get("itemId"), e)
            return None

    def close(self) -> None:
        self.session.close()
