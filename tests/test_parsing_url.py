from marktplaats_monitor.parsing import parse_search_url


def test_query_from_q_path():
    p = parse_search_url("https://www.marktplaats.nl/q/apple+homepod+mini/")
    assert p["query"] == "apple homepod mini"


def test_query_from_query_param():
    p = parse_search_url("https://www.marktplaats.nl/l/audio?query=marantz+versterker")
    assert p["query"] == "marantz versterker"


def test_query_from_q_param_takes_precedence_order():
    p = parse_search_url("https://www.marktplaats.nl/?q=sony")
    assert p["query"] == "sony"


def test_postcode_and_distance_from_fragment():
    p = parse_search_url("https://www.marktplaats.nl/q/fiets/#distanceMeters:25000|postcode:2342CM")
    assert p["query"] == "fiets"
    assert p["postcode"] == "2342 CM"
    assert p["distanceMeters"] == 25000


def test_postcode_without_radius_uses_default_km():
    p = parse_search_url(
        "https://www.marktplaats.nl/q/fiets/#postcode:1011AB", default_distance_km=30
    )
    assert p["postcode"] == "1011 AB"
    assert p["distanceMeters"] == 30_000


def test_postcode_and_distance_from_query_string():
    p = parse_search_url("https://www.marktplaats.nl/q/x/?postcode=1234AB&distanceMeters=5000")
    assert p["postcode"] == "1234 AB"
    assert p["distanceMeters"] == 5000


def test_price_hints_from_query_string():
    p = parse_search_url("https://www.marktplaats.nl/q/x/?priceFrom=1000&priceTo=5000")
    assert p["price_min_cents"] == 1000
    assert p["price_max_cents"] == 5000


def test_category_and_sort_passthrough():
    p = parse_search_url(
        "https://www.marktplaats.nl/q/x/?l1CategoryId=322&sortBy=PRICE&sortOrder=INCREASING"
    )
    assert p["l1CategoryId"] == "322"
    assert p["sortBy"] == "PRICE"
    assert p["sortOrder"] == "INCREASING"


def test_no_query_is_empty_string_not_error():
    p = parse_search_url("https://www.marktplaats.nl/l/fietsen-en-brommers/")
    assert p["query"] == ""


# --- SPA fragment edge cases -------------------------------------------------


def test_query_from_fragment_q():
    p = parse_search_url("https://www.marktplaats.nl/l/auto-s/#q:mercedes+benz")
    assert p["query"] == "mercedes benz"


def test_path_query_wins_over_fragment_q():
    p = parse_search_url("https://www.marktplaats.nl/q/fiets/#q:auto")
    assert p["query"] == "fiets"


def test_price_cents_aliases_from_fragment():
    p = parse_search_url(
        "https://www.marktplaats.nl/l/x/#PriceCentsFrom:150000|PriceCentsTo:300000"
    )
    assert p["price_min_cents"] == 150000
    assert p["price_max_cents"] == 300000


def test_price_cents_alias_from_query_string():
    p = parse_search_url("https://www.marktplaats.nl/q/x/?priceCentsFrom=2500")
    assert p["price_min_cents"] == 2500


def test_fragment_keys_are_case_insensitive():
    p = parse_search_url("https://www.marktplaats.nl/q/x/#POSTCODE:1011ab|DistanceMeters:8000")
    assert p["postcode"] == "1011 AB"
    assert p["distanceMeters"] == 8000


def test_faceted_browse_url_does_not_error_and_keeps_known_parts():
    # The exact kind of URL a user copies from a car search.
    url = (
        "https://www.marktplaats.nl/l/auto-s/mercedes-benz/f/benzine+handgeschakeld/"
        "473+535/#q:auto|f:10899|PriceCentsFrom:150000|constructionYearTo:2024|"
        "mileageFrom:20001|distanceMeters:10000|postcode:2342CM"
    )
    p = parse_search_url(url)
    assert p["query"] == "auto"
    assert p["price_min_cents"] == 150000
    assert p["postcode"] == "2342 CM"
    assert p["distanceMeters"] == 10000
    # undecodable facets are dropped, not raised
    assert "constructionYearTo" not in p
    assert "mileageFrom" not in p


def test_empty_fragment_tokens_are_safe():
    p = parse_search_url("https://www.marktplaats.nl/q/x/#|q:|postcode:1011AB|")
    assert p["query"] == "x"  # empty #q: doesn't clobber the path query
    assert p["postcode"] == "1011 AB"
