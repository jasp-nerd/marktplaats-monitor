import pytest

from marktplaats_monitor.evaluator import (
    ListingEvaluator,
    NoOpEvaluator,
    available_evaluators,
    get_evaluator,
    register_evaluator,
)
from marktplaats_monitor.models import Evaluation
from tests.conftest import make_listing


def test_noop_keeps_everything():
    ev = get_evaluator("noop")
    result = ev.evaluate(make_listing(), search=None)
    assert result.keep is True
    assert result.score is None


def test_noop_satisfies_protocol():
    assert isinstance(NoOpEvaluator(), ListingEvaluator)


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown evaluator"):
        get_evaluator("does-not-exist")


def test_register_and_resolve_custom_evaluator():
    class KeepCheap:
        def evaluate(self, listing, search):
            return Evaluation(
                keep=listing.price_cents is not None and listing.price_cents < 5000,
                score=0.5,
                label="cheap-check",
            )

    register_evaluator("keep_cheap", lambda opts: KeepCheap())
    assert "keep_cheap" in available_evaluators()

    ev = get_evaluator("keep_cheap")
    assert ev.evaluate(make_listing(cents=3000), None).keep is True
    out = ev.evaluate(make_listing(cents=9000), None)
    assert out.keep is False
    assert out.label == "cheap-check"
