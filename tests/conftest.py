import json
from pathlib import Path

import pytest

from marktplaats_monitor.models import Listing
from marktplaats_monitor.parsing import PriceParts, PriceType

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def search_response() -> dict:
    """The captured (trimmed, anonymised) /lrp/api/search payload."""
    return json.loads((FIXTURES / "search_response.json").read_text(encoding="utf-8"))


def make_listing(
    item_id: str = "m1",
    *,
    cents: int | None = 10000,
    title: str = "Test listing",
    description: str = "desc",
    price_type: PriceType = PriceType.FIXED,
) -> Listing:
    """Build a minimal :class:`Listing` for state/filter tests."""
    if cents is None:
        price = PriceParts("Bieden", 0.0, None, PriceType.BID)
    else:
        price = PriceParts(f"€ {cents / 100:.2f}", cents / 100, cents, price_type)
    return Listing(
        item_id=item_id,
        title=title,
        description=description,
        url=f"https://link.marktplaats.nl/{item_id}",
        price=price,
        location="Amsterdam",
        country="Nederland",
        distance_meters=1000,
        seller_name="Seller",
        seller_verified=False,
        posted_raw="Vandaag",
        posted_at=None,
        image_url="https://images.marktplaats.com/x.jpg",
        condition="Gebruikt",
        category_id=322,
    )


@pytest.fixture
def listing_factory():
    return make_listing
