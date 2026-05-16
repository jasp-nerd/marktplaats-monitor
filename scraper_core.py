#!/usr/bin/env python3
"""
Marktplaats Item Scraper - Core scraping functionality for any item listings.

Uses Marktplaats' own search API (https://www.marktplaats.nl/lrp/api/search)
instead of parsing HTML. The API returns clean structured JSON and natively
supports location filtering via `postcode` + `distanceMeters`, so a URL like
`https://www.marktplaats.nl/q/apple+homepod+mini/#postcode:2342CM` actually
filters by location (HTML fragments are never sent to a server, so the old
HTML scraper silently ignored the postcode).
"""

import re
import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from urllib.parse import urlsplit, parse_qs, unquote, unquote_plus

import requests

logger = logging.getLogger(__name__)

API_URL = "https://www.marktplaats.nl/lrp/api/search"
BASE_URL = "https://www.marktplaats.nl"
DEFAULT_DISTANCE_KM = 50  # used when a postcode is given but no radius


@dataclass
class ItemListing:
    """Data class representing an item listing from Marktplaats."""
    title: str
    price: str
    price_numeric: float
    location: str
    seller_name: str
    posting_date: str
    description: str
    listing_url: str
    category: str = "Unknown"
    brand: str = "Unknown"
    features: List[str] = None
    condition: str = "Unknown"
    image_url: str = ""

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.brand == "Unknown":
            self.brand = self._extract_brand()

    def _extract_brand(self) -> str:
        """Extract brand from title based on common brand names."""
        title_upper = self.title.upper()
        for brand in MarktplaatsItemScraper.COMMON_BRANDS:
            if brand.upper() in title_upper:
                return brand
        return "Unknown"


def parse_search_url(url: str, default_distance_km: int = DEFAULT_DISTANCE_KM) -> Dict[str, Any]:
    """Parse a Marktplaats search URL into search-API parameters.

    Handles the normal query path (``/q/apple+homepod+mini/``), an explicit
    ``?query=`` parameter, and the SPA fragment Marktplaats puts filters in,
    e.g. ``#postcode:2342CM`` or ``#distanceMeters:25000|postcode:2342CM``.
    URL fragments are never sent to a server, so we promote the known ones to
    real API parameters here.
    """
    parts = urlsplit(url)
    params: Dict[str, Any] = {}

    # --- search query: from /q/<words>/ path or ?query=/?q= ---
    query_params = parse_qs(parts.query)
    query = ""
    if "query" in query_params:
        query = query_params["query"][0]
    elif "q" in query_params:
        query = query_params["q"][0]
    else:
        m = re.search(r"/q/([^/]+)", parts.path)
        if m:
            query = unquote_plus(m.group(1)).replace("+", " ")
    params["query"] = query.strip()

    # --- price filters from the query string (Marktplaats uses cents) ---
    for src, dst in (("priceFrom", "priceFrom"), ("priceTo", "priceTo")):
        if src in query_params:
            params[dst] = query_params[src][0]

    # --- filters Marktplaats stores in the URL fragment (key:value|key:value) ---
    postcode = ""
    distance_meters: Optional[int] = None
    if "postcode" in query_params:
        postcode = query_params["postcode"][0]
    if "distanceMeters" in query_params:
        try:
            distance_meters = int(query_params["distanceMeters"][0])
        except (ValueError, TypeError):
            pass

    if parts.fragment:
        for token in re.split(r"[|&]", unquote(parts.fragment)):
            key, _, value = token.partition(":")
            key, value = key.strip(), value.strip()
            if not value:
                continue
            if key == "postcode":
                postcode = value
            elif key == "distanceMeters":
                try:
                    distance_meters = int(value)
                except ValueError:
                    pass
            elif key in ("priceFrom", "priceTo"):
                params[key] = value

    if postcode:
        params["postcode"] = _normalize_postcode(postcode)
        # A postcode only filters when combined with a radius. If the URL
        # didn't specify one, fall back to a sensible default.
        params["distanceMeters"] = distance_meters or default_distance_km * 1000
    elif distance_meters is not None:
        params["distanceMeters"] = distance_meters

    return params


def _normalize_postcode(postcode: str) -> str:
    """Normalize a Dutch postcode to ``1234 AB`` (Marktplaats accepts both,
    this just keeps logs/requests tidy)."""
    pc = postcode.upper().replace(" ", "")
    m = re.match(r"^(\d{4})([A-Z]{2})$", pc)
    return f"{m.group(1)} {m.group(2)}" if m else postcode.strip()


class MarktplaatsItemScraper:
    """Scraper for Marktplaats item listings backed by the search API."""

    COMMON_BRANDS = [
        'Samsung', 'LG', 'Sony', 'Philips', 'TCL', 'Hisense',
        'Panasonic', 'Sharp', 'Toshiba', 'JVC', 'Grundig',
        'Bang & Olufsen', 'Loewe', 'Xiaomi', 'OnePlus', 'Huawei',
        'Apple', 'Google', 'Amazon', 'Microsoft', 'Nintendo',
        'Dell', 'HP', 'Lenovo', 'Asus', 'Acer', 'MSI',
        'Nike', 'Adidas', 'Puma', 'Under Armour', 'New Balance',
        'BMW', 'Mercedes', 'Audi', 'Volkswagen', 'Toyota',
        'IKEA', 'Zara', 'H&M', 'Uniqlo', "Levi's"
    ]

    PAGE_SIZE = 30

    def __init__(self, default_distance_km: int = DEFAULT_DISTANCE_KM):
        self.default_distance_km = default_distance_km
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
            'Referer': BASE_URL + '/',
        })
        logger.debug("MarktplaatsItemScraper initialized (API mode)")

    def scrape_listings(self, search_url: str, max_pages: int = 3,
                        sort_by: str = "SORT_INDEX",
                        sort_order: str = "DECREASING") -> List[ItemListing]:
        """Fetch item listings for any Marktplaats search URL."""
        base_params = parse_search_url(search_url, self.default_distance_km)
        if not base_params.get("query"):
            logger.warning(f"Could not extract a search query from URL: {search_url}")

        loc = base_params.get("postcode")
        if loc:
            logger.info(f"📍 Location filter active: {loc} within "
                        f"{base_params.get('distanceMeters', 0) // 1000} km")

        all_listings: List[ItemListing] = []
        seen_ids = set()

        for page in range(max_pages):
            params = dict(base_params)
            params.update({
                "limit": self.PAGE_SIZE,
                "offset": page * self.PAGE_SIZE,
                "sortBy": sort_by,
                "sortOrder": sort_order,
            })

            try:
                resp = self.session.get(API_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed on page {page + 1}: {e}")
                break
            except ValueError as e:
                logger.error(f"API returned non-JSON response on page {page + 1}: {e}")
                break

            # `listings` are organic results, `topBlock` are sponsored ones
            # that also show up on the page; include both, de-duped by itemId.
            raw_items = (data.get("listings") or []) + (data.get("topBlock") or [])
            page_listings = []
            for item in raw_items:
                item_id = item.get("itemId")
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)
                listing = self._json_to_listing(item)
                if listing:
                    page_listings.append(listing)

            all_listings.extend(page_listings)
            logger.info(f"🔍 Page {page + 1}/{max_pages}: {len(page_listings)} listings "
                        f"(total so far: {len(all_listings)})")

            total = data.get("totalResultCount", 0)
            if not page_listings or (page + 1) * self.PAGE_SIZE >= total:
                break
            time.sleep(1)  # be polite to the server

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    # Backwards-compatible alias
    def fetch_listings(self, search_url: str, max_pages: int = 1, **kwargs) -> List[ItemListing]:
        return self.scrape_listings(search_url, max_pages=max_pages, **kwargs)

    def _json_to_listing(self, item: Dict[str, Any]) -> Optional[ItemListing]:
        """Convert one API listing object into an ItemListing."""
        try:
            title = (item.get("title") or "").strip()
            if not title:
                return None

            price_info = item.get("priceInfo") or {}
            price, price_numeric = self._format_price(price_info)

            loc = item.get("location") or {}
            location = loc.get("cityName") or loc.get("countryName") or "Locatie onbekend"

            seller = (item.get("sellerInformation") or {}).get("sellerName") or "Zie advertentie"

            posting_date = item.get("date") or "Datum onbekend"

            description = (item.get("categorySpecificDescription")
                           or item.get("description") or "").strip()
            if len(description) > 500:
                description = description[:497] + "..."
            if not description:
                description = "Zie advertentie voor volledige beschrijving"

            vip_url = item.get("vipUrl") or ""
            if vip_url.startswith("/"):
                listing_url = BASE_URL + vip_url
            elif vip_url.startswith("http"):
                listing_url = vip_url
            else:
                seller_url = (item.get("sellerInformation") or {}).get("sellerWebsiteUrl")
                listing_url = seller_url or "# External listing - no direct link available"

            image_url = ""
            images = item.get("imageUrls") or []
            if images:
                image_url = images[0]
                if image_url.startswith("//"):
                    image_url = "https:" + image_url

            condition = "Unknown"
            for attr in item.get("attributes") or []:
                if attr.get("key") == "condition" and attr.get("value"):
                    condition = attr["value"]
                    break

            return ItemListing(
                title=title,
                price=price,
                price_numeric=price_numeric,
                location=location,
                seller_name=seller,
                posting_date=posting_date,
                description=description,
                listing_url=listing_url,
                condition=condition,
                image_url=image_url,
            )
        except Exception as e:
            logger.error(f"Error converting API listing: {e}")
            return None

    @staticmethod
    def _format_price(price_info: Dict[str, Any]) -> tuple:
        """Map Marktplaats priceInfo to a (display_string, numeric) pair."""
        cents = price_info.get("priceCents")
        price_type = price_info.get("priceType", "")

        def euro(c: int) -> str:
            return f"€ {c // 100},{c % 100:02d}"

        labels = {
            "FAST_BID": "Bieden",
            "MIN_BID": "Bieden vanaf",
            "RESERVED": "Gereserveerd",
            "FREE": "Gratis",
            "EXCHANGE": "Ruilen",
            "NOTK": "N.o.t.k.",
            "ON_REQUEST": "Op aanvraag",
            "SEE_DESCRIPTION": "Zie omschrijving",
        }

        if price_type == "FIXED" and cents is not None:
            return euro(cents), cents / 100.0
        if price_type in ("MIN_BID",) and cents:
            return f"{labels[price_type]} {euro(cents)}", cents / 100.0
        if price_type in labels:
            return labels[price_type], 0.0
        if cents:
            return euro(cents), cents / 100.0
        return "Prijs onbekend", 0.0

    def get_listing_details(self, listing_url: str) -> Dict[str, Any]:
        """Kept for API compatibility; the search API already returns enough
        detail per listing, so individual pages are not fetched."""
        return {}

    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("MarktplaatsItemScraper session closed")
