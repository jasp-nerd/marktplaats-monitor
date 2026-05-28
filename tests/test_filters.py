import re

import pytest

from marktplaats_monitor.filters import ListingFilter
from tests.conftest import make_listing


def test_price_bounds():
    f = ListingFilter.build(price_min_cents=5000, price_max_cents=15000)
    assert f.passes(make_listing(cents=10000))
    assert not f.passes(make_listing(cents=4000))
    assert not f.passes(make_listing(cents=20000))


def test_non_numeric_price_fails_when_bound_set():
    f = ListingFilter.build(price_max_cents=15000)
    assert not f.passes(make_listing(cents=None))  # "Bieden"


def test_non_numeric_price_ok_when_no_bound():
    f = ListingFilter.build()
    assert f.passes(make_listing(cents=None))


def test_include_keywords_any_match():
    f = ListingFilter.build(include_keywords=["homepod", "sonos"])
    assert f.passes(make_listing(title="Apple HomePod mini wit"))
    assert not f.passes(make_listing(title="Google Nest Mini"))


def test_include_is_case_insensitive_and_checks_description():
    f = ListingFilter.build(include_keywords=["GAZELLE"])
    lst = make_listing(title="Damesfiets", description="Mooie gazelle fiets")
    assert f.passes(lst)


def test_exclude_regex_drops_match():
    f = ListingFilter.build(exclude_keywords=[r"\bdefect\b", "kapot"])
    assert not f.passes(make_listing(title="iPhone defect scherm"))
    assert not f.passes(make_listing(title="Kapotte telefoon"))
    assert f.passes(make_listing(title="iPhone werkend"))


def test_invalid_exclude_regex_raises_with_pattern():
    with pytest.raises(re.error, match=r"\[unclosed"):
        ListingFilter.build(exclude_keywords=["[unclosed"])


def test_no_filters_passes_everything():
    assert ListingFilter.build().passes(make_listing())
