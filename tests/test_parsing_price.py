from marktplaats_monitor.parsing import PriceType, format_price


def test_fixed_price():
    pp = format_price({"priceCents": 9000, "priceType": "FIXED"})
    assert pp.cents == 9000
    assert pp.euros == 90.0
    assert pp.display == "€ 90,00"
    assert pp.price_type is PriceType.FIXED


def test_fixed_price_with_odd_cents():
    pp = format_price({"priceCents": 12345, "priceType": "FIXED"})
    assert pp.display == "€ 123,45"
    assert pp.cents == 12345


def test_bid_from_keeps_numeric_cents():
    pp = format_price({"priceCents": 5000, "priceType": "MIN_BID"})
    assert pp.cents == 5000
    assert pp.display == "Bieden vanaf € 50,00"
    assert pp.price_type is PriceType.BID_FROM


def test_free_has_no_cents():
    pp = format_price({"priceCents": 0, "priceType": "FREE"})
    assert pp.cents is None
    assert pp.display == "Gratis"
    assert pp.price_type is PriceType.FREE


def test_bid_has_no_cents():
    pp = format_price({"priceCents": 0, "priceType": "FAST_BID"})
    assert pp.cents is None
    assert pp.display == "Bieden"
    assert pp.price_type is PriceType.BID


def test_notk():
    pp = format_price({"priceType": "NOTK"})
    assert pp.display == "N.o.t.k."
    assert pp.cents is None


def test_unknown_type_with_price_shows_price():
    pp = format_price({"priceCents": 2500, "priceType": "SOMETHING_NEW"})
    assert pp.price_type is PriceType.UNKNOWN
    assert pp.cents == 2500
    assert pp.display == "€ 25,00"


def test_missing_price_info():
    pp = format_price(None)
    assert pp.display == "Prijs onbekend"
    assert pp.cents is None
