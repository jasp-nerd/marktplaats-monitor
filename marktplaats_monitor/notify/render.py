"""Shared notification rendering (title + markdown body).

Used by the Apprise backend directly and as the description source for the
native Discord embed.
"""

from __future__ import annotations

from marktplaats_monitor.models import EventKind, NotifyEvent


def _euro(cents: int | None) -> str:
    return f"€ {cents // 100},{cents % 100:02d}" if isinstance(cents, int) else "?"


def build_title(event: NotifyEvent) -> str:
    if event.kind is EventKind.PRICE_DROP:
        return f"📉 Prijsverlaging: {event.search_name}"
    return f"🆕 Nieuw: {event.search_name}"


def build_body(event: NotifyEvent) -> str:
    """A compact markdown body that renders well across services."""
    lst = event.listing
    lines: list[str] = [f"**{lst.title}**"]

    if event.kind is EventKind.PRICE_DROP:
        lines.append(f"💸 **{_euro(event.old_price_cents)} → {_euro(event.new_price_cents)}**")
    else:
        lines.append(f"💰 **{lst.price.display}**")

    meta = [f"📍 {lst.location}"]
    if lst.distance_meters is not None:
        meta.append(f"~{round(lst.distance_meters / 1000)} km")
    if lst.posted_raw:
        meta.append(f"📅 {lst.posted_raw}")
    if lst.condition:
        meta.append(f"🏷️ {lst.condition}")
    lines.append(" · ".join(meta))

    if lst.seller_name:
        verified = " ✅" if lst.seller_verified else ""
        lines.append(f"👤 {lst.seller_name}{verified}")

    if lst.description:
        snippet = lst.description.strip()
        if len(snippet) > 300:
            snippet = snippet[:297] + "..."
        lines.append(f"\n{snippet}")

    lines.append(f"\n🔗 {lst.url}")
    return "\n".join(lines)
