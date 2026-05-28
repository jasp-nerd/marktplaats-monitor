"""Client-side listing filters.

Price is also filtered server-side via ``attributeRanges[]``; this is the
safety net (the API can include slightly out-of-range or non-fixed-price
items, and keyword filtering has no server equivalent).

Rules:
* **price** — a numeric price is required to pass when any price bound is set;
  listings with no concrete price (``Bieden`` / ``Gratis`` / ``N.o.t.k.``)
  do not satisfy a numeric range and are dropped.
* **include_keywords** — if non-empty, at least one (case-insensitive
  substring) must appear in the title or description.
* **exclude_keywords** — regexes; if any matches the title or description the
  listing is dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from marktplaats_monitor.models import Listing


@dataclass
class ListingFilter:
    price_min_cents: int | None = None
    price_max_cents: int | None = None
    include_keywords: tuple[str, ...] = ()
    exclude_patterns: tuple[re.Pattern[str], ...] = ()

    @classmethod
    def build(
        cls,
        *,
        price_min_cents: int | None = None,
        price_max_cents: int | None = None,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
    ) -> ListingFilter:
        """Build a filter, compiling exclude regexes once.

        Raises ``re.error`` with the offending pattern if one is invalid, so
        config validation can fail fast.
        """
        compiled: list[re.Pattern[str]] = []
        for pat in exclude_keywords or []:
            try:
                compiled.append(re.compile(pat, re.IGNORECASE))
            except re.error as e:
                raise re.error(f"invalid exclude_keywords regex {pat!r}: {e}") from e
        return cls(
            price_min_cents=price_min_cents,
            price_max_cents=price_max_cents,
            include_keywords=tuple(k.lower() for k in (include_keywords or []) if k),
            exclude_patterns=tuple(compiled),
        )

    def passes(self, listing: Listing) -> bool:
        if self.price_min_cents is not None or self.price_max_cents is not None:
            cents = listing.price_cents
            if cents is None:
                return False
            if self.price_min_cents is not None and cents < self.price_min_cents:
                return False
            if self.price_max_cents is not None and cents > self.price_max_cents:
                return False

        haystack = f"{listing.title}\n{listing.description}"
        if self.include_keywords and not any(k in haystack.lower() for k in self.include_keywords):
            return False
        return all(p.search(haystack) is None for p in self.exclude_patterns)
