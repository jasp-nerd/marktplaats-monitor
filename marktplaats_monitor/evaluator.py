"""Pluggable listing-evaluator hook.

The pipeline calls ``evaluate()`` for every listing that survives the cheap
price/keyword filters and **before** state/dedup, so a future paid LLM scorer
only ever sees pre-filtered listings. The default is a no-op pass-through.

Adding a real scorer later requires **no pipeline change**: implement the
``ListingEvaluator`` protocol, register it, and set ``evaluator.type`` (plus
``evaluator.options``) in ``config.yaml``. A planned example is a genAI scorer
that rates how well a listing fits the search and whether the price is fair —
see the README roadmap. Nothing here calls an LLM.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from marktplaats_monitor.models import Evaluation, Listing


@runtime_checkable
class ListingEvaluator(Protocol):
    def evaluate(self, listing: Listing, search: Any) -> Evaluation:
        """Return an :class:`Evaluation`. ``keep=False`` drops the listing."""
        ...


class NoOpEvaluator:
    """Keeps every listing; assigns no score."""

    def evaluate(self, listing: Listing, search: Any) -> Evaluation:  # noqa: ARG002
        return Evaluation(keep=True)


EvaluatorFactory = Any  # callable(options: dict) -> ListingEvaluator

_REGISTRY: dict[str, EvaluatorFactory] = {
    "noop": lambda _options: NoOpEvaluator(),
}


def register_evaluator(name: str, factory: EvaluatorFactory) -> None:
    """Register an evaluator factory under ``name`` (for future plugins)."""
    _REGISTRY[name] = factory


def available_evaluators() -> list[str]:
    return sorted(_REGISTRY)


def get_evaluator(type_: str = "noop", options: dict | None = None) -> ListingEvaluator:
    """Resolve an evaluator by name; raises ValueError for an unknown name."""
    factory = _REGISTRY.get(type_)
    if factory is None:
        raise ValueError(f"Unknown evaluator type {type_!r}; available: {available_evaluators()}")
    return factory(options or {})
