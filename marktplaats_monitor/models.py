"""Plain data types shared across the package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from marktplaats_monitor.parsing import PriceParts


@dataclass(frozen=True)
class Listing:
    """A normalized Marktplaats listing."""

    item_id: str
    title: str
    description: str
    url: str
    price: PriceParts
    location: str
    country: str
    distance_meters: int | None
    seller_name: str
    seller_verified: bool
    posted_raw: str
    posted_at: date | None
    image_url: str
    condition: str
    category_id: int | None
    is_sponsored: bool = False  # came from the API ``topBlock``

    @property
    def price_cents(self) -> int | None:
        return self.price.cents


class EventKind(StrEnum):
    NEW = "new"
    PRICE_DROP = "price_drop"


@dataclass(frozen=True)
class NotifyEvent:
    """Something worth notifying about for a given search."""

    kind: EventKind
    listing: Listing
    search_id: str
    search_name: str
    old_price_cents: int | None = None  # set for PRICE_DROP
    new_price_cents: int | None = None  # set for PRICE_DROP


@dataclass(frozen=True)
class Evaluation:
    """Result of a :class:`~marktplaats_monitor.evaluator.ListingEvaluator`."""

    keep: bool = True
    score: float | None = None
    label: str | None = None
    reason: str | None = None


@dataclass
class RunStats:
    """Per-search outcome of one polling cycle (persisted to ``runs``)."""

    search_id: str
    fetched: int = 0
    passed_filter: int = 0
    new_count: int = 0
    drop_count: int = 0
    error: str | None = None
    notify_failures: list[str] = field(default_factory=list)
