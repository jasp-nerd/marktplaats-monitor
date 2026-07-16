import textwrap

import pytest

from marktplaats_monitor.config import ConfigError, load_config


def write(tmp_path, body: str):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_valid_config_merges_and_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://ntfy.sh/topic")
    cfg = write(
        tmp_path,
        """
        defaults:
          check_interval: 90
          distance_km: 50
          notify:
            backend: apprise
            apprise_urls: ["env:APPRISE_URLS"]
        searches:
          - id: homepod
            name: HomePod
            url: https://www.marktplaats.nl/q/homepod/
            price_min: 30
            price_max: 120
            condition: USED
            category: "Fietsen en Brommers"
        """,
    )
    c = load_config(cfg)
    assert c.check_interval == 90
    assert len(c.searches) == 1
    s = c.searches[0]
    assert s.price_min_cents == 3000
    assert s.price_max_cents == 12000
    assert s.condition == "used"
    assert s.category_params and "l1CategoryId" in s.category_params
    assert s.distance_km == 50  # inherited from defaults
    assert s.notify.apprise_urls == ["ntfy://ntfy.sh/topic"]


def test_per_search_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://x/y")
    cfg = write(
        tmp_path,
        """
        defaults:
          distance_km: 50
          notify: {apprise_urls: ["env:APPRISE_URLS"], mention: none}
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            distance_km: 5
            notify: {mention: everyone}
        """,
    )
    s = load_config(cfg).searches[0]
    assert s.distance_km == 5
    assert s.notify.mention == "everyone"
    assert s.notify.apprise_urls == ["ntfy://x/y"]  # inherited


def test_exclude_promoted_defaults_true_and_is_overridable(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://x/y")
    cfg = write(
        tmp_path,
        """
        defaults:
          notify: {apprise_urls: ["env:APPRISE_URLS"]}
        searches:
          - id: default-on
            query: tv
          - id: opted-out
            query: tv
            exclude_promoted: false
        """,
    )
    searches = {s.id: s for s in load_config(cfg).searches}
    assert searches["default-on"].exclude_promoted is True  # safe default
    assert searches["opted-out"].exclude_promoted is False


def test_missing_secret_names_the_var(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            notify: {apprise_urls: ["env:NOPE_MISSING"]}
        """,
    )
    with pytest.raises(ConfigError, match="NOPE_MISSING"):
        load_config(cfg)


def test_bad_exclude_regex(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://x/y")
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            exclude_keywords: ["[oops"]
            notify: {apprise_urls: ["env:APPRISE_URLS"]}
        """,
    )
    with pytest.raises(ConfigError, match="invalid exclude_keywords regex"):
        load_config(cfg)


def test_duplicate_and_invalid_ids(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: dup
            url: https://www.marktplaats.nl/q/a/
          - id: dup
            url: https://www.marktplaats.nl/q/b/
          - id: "Bad Id"
            url: https://www.marktplaats.nl/q/c/
        """,
    )
    with pytest.raises(ConfigError) as e:
        load_config(cfg)
    assert "duplicate search id: dup" in str(e.value)
    assert "invalid or missing id" in str(e.value)


def test_price_min_gt_max(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            price_min: 200
            price_max: 100
        """,
    )
    with pytest.raises(ConfigError, match="price_min"):
        load_config(cfg)


def test_poll_interval_parsed_and_validated(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            poll_interval: 7
          - id: b
            url: https://www.marktplaats.nl/q/b/
        """,
    )
    c = load_config(cfg)
    assert c.searches[0].poll_interval == 7
    assert c.searches[1].poll_interval is None

    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            poll_interval: 0
        """,
    )
    with pytest.raises(ConfigError, match="poll_interval"):
        load_config(cfg)


def test_unknown_condition(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            condition: brokenish
        """,
    )
    with pytest.raises(ConfigError, match="unknown condition"):
        load_config(cfg)


def test_unknown_category_is_warning_not_error(tmp_path, caplog):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            category: "Totally Not A Category"
        """,
    )
    c = load_config(cfg)
    assert c.searches[0].category_name is None
    assert c.searches[0].category_params is None


def test_discord_native_requires_webhook(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            notify: {backend: discord_native}
        """,
    )
    with pytest.raises(ConfigError, match="discord_native but no discord_webhook"):
        load_config(cfg)


def test_empty_searches(tmp_path):
    cfg = write(tmp_path, "defaults: {}\nsearches: []\n")
    with pytest.raises(ConfigError, match="No searches"):
        load_config(cfg)


def test_invalid_backend_and_mention(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://x/y")
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            url: https://www.marktplaats.nl/q/a/
            notify:
              backend: carrierpigeon
              mention: shout
              apprise_urls: ["env:APPRISE_URLS"]
        """,
    )
    with pytest.raises(ConfigError) as e:
        load_config(cfg)
    assert "notify.backend" in str(e.value)
    assert "notify.mention" in str(e.value)


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_query_only_search_is_valid(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            query: "mercedes benz"
            postcode: "1011 AB"
            distance_km: 10
        """,
    )
    s = load_config(cfg).searches[0]
    assert s.url is None
    assert s.query == "mercedes benz"
    assert s.postcode == "1011 AB"


def test_search_needs_url_query_or_category(tmp_path):
    cfg = write(
        tmp_path,
        """
        searches:
          - id: a
            name: "no target"
        """,
    )
    with pytest.raises(ConfigError, match="at least one of 'url', 'query', or 'category'"):
        load_config(cfg)
