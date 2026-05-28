from marktplaats_monitor.categories import (
    category_api_params,
    list_l1,
    list_l2,
    resolve_category,
)


def test_resolve_l1_case_insensitive():
    c = resolve_category("Antiek en Kunst")
    assert c is not None
    assert c.level == 1
    assert c.id == 1
    assert resolve_category("antiek en kunst") == c


def test_resolve_l2_has_parent():
    c = resolve_category("Antiek | Bestek")
    assert c is not None
    assert c.level == 2
    assert c.id == 2
    assert c.parent_name == "Antiek en Kunst"


def test_unknown_returns_none_not_exception():
    assert resolve_category("Totally Made Up Category") is None
    assert resolve_category("") is None


def test_category_api_params_l1():
    c = resolve_category("Antiek en Kunst")
    assert category_api_params(c) == {"l1CategoryId": "1"}


def test_category_api_params_l2_includes_parent_l1():
    c = resolve_category("Antiek | Bestek")
    params = category_api_params(c)
    assert params["l2CategoryId"] == "2"
    assert params["l1CategoryId"] == "1"  # parent "Antiek en Kunst"


def test_listings_non_empty_and_sorted():
    l1 = list_l1()
    assert len(l1) == 36
    assert [c.name for c in l1] == sorted(c.name for c in l1)

    bikes = list_l2("Antiek en Kunst")
    assert bikes
    assert all(c.parent_name == "Antiek en Kunst" for c in bikes)
