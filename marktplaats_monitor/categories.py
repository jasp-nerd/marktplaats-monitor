"""Marktplaats category lookup (vendored, adapted).

The category id <-> name map and the lookup approach are adapted from
**marktplaats-py** (https://github.com/jensjeflensje/marktplaats-py),
``src/marktplaats/categories.py`` + ``l1_categories.json`` /
``l2_categories.json``, v0.4.0, MIT License, Copyright (c) 2023 Jens de Ruiter.
See ``THIRD_PARTY_NOTICES.md`` for the full license and refresh policy.

Adapted for this project: simplified to a single ``Category`` value type and
a non-raising ``resolve_category()`` (returns ``None`` for unknown names so
the config layer can warn and continue instead of crashing a long-running
monitor).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

__all__ = [
    "Category",
    "category_api_params",
    "list_l1",
    "list_l2",
    "resolve_category",
]


@dataclass(frozen=True)
class Category:
    """A resolved Marktplaats category.

    ``level`` is 1 or 2. For an L2 category, ``parent_name`` is the L1 name.
    """

    level: int
    id: int
    name: str
    parent_name: str | None = None


@lru_cache(maxsize=1)
def _l1_raw() -> dict[str, dict]:
    data = resources.files("marktplaats_monitor.data").joinpath("l1_categories.json")
    return json.loads(data.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _l2_raw() -> dict[str, dict]:
    data = resources.files("marktplaats_monitor.data").joinpath("l2_categories.json")
    return json.loads(data.read_text(encoding="utf-8"))


def resolve_category(name: str) -> Category | None:
    """Resolve a category by (case-insensitive) name.

    L1 is tried first, then L2. Returns ``None`` if the name is unknown so the
    caller can warn and treat it as "no category filter".
    """
    if not name:
        return None
    key = name.strip().lower()

    l1 = _l1_raw().get(key)
    if l1 is not None:
        return Category(level=1, id=int(l1["id"]), name=l1["name"])

    l2 = _l2_raw().get(key)
    if l2 is not None:
        return Category(
            level=2,
            id=int(l2["id"]),
            name=l2["name"],
            parent_name=l2["parent"],
        )
    return None


def category_api_params(category: Category) -> dict[str, str]:
    """Map a resolved category to Marktplaats search-API params.

    L1 -> ``{l1CategoryId}``. L2 -> ``{l1CategoryId (parent), l2CategoryId}``.
    """
    if category.level == 1:
        return {"l1CategoryId": str(category.id)}

    params = {"l2CategoryId": str(category.id)}
    if category.parent_name:
        parent = _l1_raw().get(category.parent_name.strip().lower())
        if parent is not None:
            params["l1CategoryId"] = str(parent["id"])
    return params


def list_l1() -> list[Category]:
    """All L1 categories, sorted by name (for a future ``--list-categories``)."""
    out = [Category(level=1, id=int(c["id"]), name=c["name"]) for c in _l1_raw().values()]
    return sorted(out, key=lambda c: c.name)


def list_l2(parent_name: str | None = None) -> list[Category]:
    """All L2 categories, optionally filtered by L1 parent name."""
    out = [
        Category(level=2, id=int(c["id"]), name=c["name"], parent_name=c["parent"])
        for c in _l2_raw().values()
    ]
    if parent_name:
        pn = parent_name.strip().lower()
        out = [c for c in out if (c.parent_name or "").lower() == pn]
    return sorted(out, key=lambda c: c.name)
