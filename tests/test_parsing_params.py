from datetime import datetime

from marktplaats_monitor.parsing import (
    build_api_params,
    build_base_params,
    parse_search_url,
)


def test_base_from_query_only():
    base = build_base_params(query="mercedes benz")
    assert base["query"] == "mercedes benz"
    assert "postcode" not in base


def test_base_from_url_only():
    base = build_base_params(url="https://www.marktplaats.nl/q/fiets/")
    assert base["query"] == "fiets"


def test_config_query_overrides_url_query():
    base = build_base_params(url="https://www.marktplaats.nl/q/fiets/", query="racefiets")
    assert base["query"] == "racefiets"


def test_config_postcode_applies_without_url():
    base = build_base_params(query="bankstel", postcode="1011ab", distance_km=15)
    assert base["postcode"] == "1011 AB"
    assert base["distanceMeters"] == 15000


def test_config_postcode_overrides_url_postcode():
    base = build_base_params(
        url="https://www.marktplaats.nl/q/x/#postcode:2000AA|distanceMeters:9000",
        postcode="3000BB",
    )
    assert base["postcode"] == "3000 BB"
    # keeps the URL's explicit radius rather than re-defaulting
    assert base["distanceMeters"] == 9000


def test_base_empty_when_nothing_given():
    assert build_base_params() == {"query": ""}


def test_defaults_and_constant_params():
    base = parse_search_url("https://www.marktplaats.nl/q/fiets/")
    p = build_api_params(base, limit=30, offset=0)
    assert p["query"] == "fiets"
    assert p["limit"] == 30
    assert p["offset"] == 0
    assert p["searchInTitleAndDescription"] == "true"
    assert p["viewOptions"] == "list-view"
    assert p["sortBy"] == "SORT_INDEX"  # Marktplaats UI's "Nieuwste eerst"
    assert p["sortOrder"] == "DECREASING"


def test_postcode_and_distance_carried_through():
    base = parse_search_url(
        "https://www.marktplaats.nl/q/fiets/#postcode:1011AB|distanceMeters:7000"
    )
    p = build_api_params(base, limit=10, offset=10)
    assert p["postcode"] == "1011 AB"
    assert p["distanceMeters"] == 7000
    assert p["offset"] == 10


def test_price_range_config_min_overrides_url_max_kept():
    base = parse_search_url("https://www.marktplaats.nl/q/x/?priceFrom=1000&priceTo=2000")
    # config sets only min; max unset (None) -> keep the URL's max (documented).
    p = build_api_params(base, limit=1, offset=0, price_min_cents=5000, price_max_cents=None)
    assert p["attributeRanges[]"] == ["PriceCents:5000:2000"]


def test_price_range_open_upper_bound_when_no_url_max():
    base = parse_search_url("https://www.marktplaats.nl/q/x/")
    p = build_api_params(base, limit=1, offset=0, price_min_cents=5000)
    assert p["attributeRanges[]"] == ["PriceCents:5000:null"]


def test_price_range_from_url_when_no_override():
    base = parse_search_url("https://www.marktplaats.nl/q/x/?priceFrom=1000&priceTo=2000")
    p = build_api_params(base, limit=1, offset=0)
    assert p["attributeRanges[]"] == ["PriceCents:1000:2000"]


def test_condition_and_offered_since():
    base = parse_search_url("https://www.marktplaats.nl/q/x/")
    since = datetime(2026, 5, 1, 0, 0, 0)
    p = build_api_params(base, limit=1, offset=0, condition="used", offered_since=since)
    assert p["attributesById[]"] == [32]
    assert p["attributesByKey[]"] == [f"offeredSince:{int(since.timestamp()) * 1000}"]


def test_unknown_condition_is_ignored():
    base = parse_search_url("https://www.marktplaats.nl/q/x/")
    p = build_api_params(base, limit=1, offset=0, condition="banana")
    assert "attributesById[]" not in p


def test_category_params_override_url_category():
    base = parse_search_url("https://www.marktplaats.nl/q/x/?l1CategoryId=999")
    p = build_api_params(
        base, limit=1, offset=0, category_params={"l1CategoryId": "322", "l2CategoryId": "1740"}
    )
    assert p["l1CategoryId"] == "322"
    assert p["l2CategoryId"] == "1740"


def test_url_sort_overrides_default():
    base = parse_search_url("https://www.marktplaats.nl/q/x/?sortBy=PRICE&sortOrder=INCREASING")
    p = build_api_params(base, limit=1, offset=0)
    assert p["sortBy"] == "PRICE"
    assert p["sortOrder"] == "INCREASING"
