from datetime import date, datetime, timedelta

from marktplaats_monitor.parsing import parse_dutch_date


def test_vandaag():
    assert parse_dutch_date("Vandaag") == datetime.now().date()


def test_gisteren():
    assert parse_dutch_date("Gisteren") == (datetime.now() - timedelta(days=1)).date()


def test_eergisteren():
    assert parse_dutch_date("Eergisteren") == (datetime.now() - timedelta(days=2)).date()


def test_explicit_dutch_month():
    assert parse_dutch_date("10 mrt 24") == date(2024, 3, 10)
    assert parse_dutch_date("1 mei 23") == date(2023, 5, 1)


def test_whitespace_tolerated():
    assert parse_dutch_date("  Vandaag  ") == datetime.now().date()


def test_garbage_returns_none():
    assert parse_dutch_date("not a date") is None
    assert parse_dutch_date("") is None
    assert parse_dutch_date(None) is None
