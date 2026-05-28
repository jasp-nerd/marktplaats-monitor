import copy
from datetime import datetime

import pytest
import requests

from marktplaats_monitor.client import MarktplaatsClient


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("marktplaats_monitor.client.time.sleep", lambda *_: None)


def test_search_parses_fixture(search_response, monkeypatch):
    # exclude_promoted=False here so all 3 organic (incl. the DAGTOPPER one)
    # parse — this test is about field parsing, not promo filtering.
    client = MarktplaatsClient(exclude_promoted=False)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(search_response))

    listings = client.search("https://www.marktplaats.nl/q/apple+homepod+mini/")

    assert len(listings) == 3  # topBlock excluded by default
    first = listings[0]
    raw_first = search_response["listings"][0]
    assert first.item_id == raw_first["itemId"]
    assert first.price.price_type.value == raw_first["priceInfo"]["priceType"]
    assert first.image_url.startswith("https://images.marktplaats.com")
    assert "#" not in first.image_url
    assert first.location
    assert first.posted_at is not None  # "Vandaag" -> today
    assert first.url.startswith("https://")
    assert first.is_sponsored is False


def test_topblock_included_when_flag_off(search_response, monkeypatch):
    client = MarktplaatsClient(exclude_topblock=False, exclude_promoted=False)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(search_response))

    listings = client.search("https://www.marktplaats.nl/q/x/")
    assert len(listings) == 5  # 3 organic + 2 sponsored
    assert sum(1 for x in listings if x.is_sponsored) == 2


def test_dedupe_by_item_id(search_response, monkeypatch):
    payload = copy.deepcopy(search_response)
    # make a topBlock item share an id with an organic listing
    payload["topBlock"][0]["itemId"] = payload["listings"][0]["itemId"]
    client = MarktplaatsClient(exclude_topblock=False, exclude_promoted=False)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(payload))

    listings = client.search("https://www.marktplaats.nl/q/x/")
    ids = [x.item_id for x in listings]
    assert len(ids) == len(set(ids))


def test_retry_then_success(search_response, monkeypatch):
    client = MarktplaatsClient(max_retries=2)
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("boom")
        return FakeResponse(search_response)

    monkeypatch.setattr(client.session, "get", flaky)
    listings = client.search("https://www.marktplaats.nl/q/x/")
    assert calls["n"] == 2
    assert listings


def test_retry_on_429_honors_retry_after(search_response, monkeypatch):
    client = MarktplaatsClient(max_retries=2)
    seq = [
        FakeResponse(status_code=429, headers={"Retry-After": "3"}),
        FakeResponse(search_response),
    ]
    slept = []
    monkeypatch.setattr("marktplaats_monitor.client.time.sleep", lambda s: slept.append(s))
    monkeypatch.setattr(client.session, "get", lambda *a, **k: seq.pop(0))

    listings = client.search("https://www.marktplaats.nl/q/x/")
    assert listings
    assert slept == [3.0]


def test_gives_up_after_max_retries(monkeypatch):
    client = MarktplaatsClient(max_retries=2)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(status_code=503))
    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        client.search("https://www.marktplaats.nl/q/x/")


def test_non_retryable_4xx_raises(monkeypatch):
    client = MarktplaatsClient()
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(status_code=404))
    with pytest.raises(requests.HTTPError):
        client.search("https://www.marktplaats.nl/q/x/")


def test_pagination_uses_offset(monkeypatch):
    page1 = {
        "listings": [{"itemId": f"m{i}", "title": f"t{i}", "priceInfo": {}} for i in range(30)],
        "totalResultCount": 45,
    }
    page2 = {
        "listings": [{"itemId": f"n{i}", "title": f"u{i}", "priceInfo": {}} for i in range(15)],
        "totalResultCount": 45,
    }
    seq = [FakeResponse(page1), FakeResponse(page2)]
    offsets = []

    client = MarktplaatsClient(page_size=30)

    def capture(url, params=None, timeout=None):
        offsets.append(params["offset"])
        return seq.pop(0)

    monkeypatch.setattr(client.session, "get", capture)
    listings = client.search("https://www.marktplaats.nl/q/x/", max_pages=3)
    assert offsets == [0, 30]
    assert len(listings) == 45


def test_search_by_query_without_url(search_response, monkeypatch):
    client = MarktplaatsClient()
    captured = {}

    def capture(url, params=None, timeout=None):
        captured.update(params)
        return FakeResponse(search_response)

    monkeypatch.setattr(client.session, "get", capture)
    listings = client.search(query="mercedes benz", postcode="1011AB")
    assert listings
    assert captured["query"] == "mercedes benz"
    assert captured["postcode"] == "1011 AB"
    assert captured["distanceMeters"] == 50_000  # default_distance_km * 1000


def test_offered_since_passes_through(search_response, monkeypatch):
    client = MarktplaatsClient()
    captured = {}

    def capture(url, params=None, timeout=None):
        captured.update(params)
        return FakeResponse(search_response)

    monkeypatch.setattr(client.session, "get", capture)
    client.search(
        "https://www.marktplaats.nl/q/x/",
        offered_since=datetime(2026, 5, 1),
        condition="used",
    )
    assert "attributesByKey[]" in captured
    assert captured["attributesById[]"] == [32]


def test_default_sort_is_sort_index_descending(search_response, monkeypatch):
    # Marktplaats UI's "Nieuwste eerst" — strict chronological newest-first.
    # OPTIMIZED is the *relevance* sort (heavy date-inversions); wrong here.
    client = MarktplaatsClient()
    captured = {}

    def capture(url, params=None, timeout=None):
        captured.update(params)
        return FakeResponse(search_response)

    monkeypatch.setattr(client.session, "get", capture)
    client.search(query="apple homepod")
    assert captured["sortBy"] == "SORT_INDEX"
    assert captured["sortOrder"] == "DECREASING"


def test_exclude_promoted_default_drops_dagtopper(search_response, monkeypatch):
    # Fixture organic: 1 DAGTOPPER (m2400411641) + 2 NONE. Default filters it.
    client = MarktplaatsClient()  # exclude_promoted defaults True
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(search_response))

    listings = client.search(query="tv")
    ids = {x.item_id for x in listings}
    assert len(listings) == 2
    assert "m2400411641" not in ids  # the DAGTOPPER organic listing


def test_exclude_promoted_false_keeps_dagtopper(search_response, monkeypatch):
    client = MarktplaatsClient(exclude_promoted=False)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(search_response))

    listings = client.search(query="tv")
    assert len(listings) == 3
    assert "m2400411641" in {x.item_id for x in listings}


def test_promoted_filter_applies_to_organic_not_sponsored(search_response, monkeypatch):
    # exclude_promoted only touches organic results; explicitly-kept topBlock
    # sponsored items (TOPADVERTENTIE) are governed by exclude_topblock alone.
    client = MarktplaatsClient(exclude_topblock=False, exclude_promoted=True)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(search_response))

    listings = client.search(query="tv")
    ids = {x.item_id for x in listings}
    assert "m2400411641" not in ids  # organic DAGTOPPER dropped
    assert sum(1 for x in listings if x.is_sponsored) == 2  # sponsored kept
    assert len(listings) == 4  # 2 organic NONE + 2 sponsored
