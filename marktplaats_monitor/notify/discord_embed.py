"""Opt-in native Discord rich-embed renderer + sender.

A multi-field embed for users who set ``notify.backend: discord_native``.
Mentions are configurable and default to none (``@everyone`` is never forced).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests

from marktplaats_monitor.models import EventKind, NotifyEvent

logger = logging.getLogger(__name__)

_COLOR_NEW = 0x1E90FF
_COLOR_DROP = 0x2ECC71


def resolve_mention(mention: str) -> tuple[str | None, dict]:
    """Map a config ``mention`` to (content, allowed_mentions).

    ``none`` (default) suppresses pings even if text contains ``@everyone``.
    Accepts ``none`` | ``everyone`` | ``here`` | ``role:<id>``.
    """
    m = (mention or "none").strip().lower()
    if m == "everyone":
        return "@everyone", {"parse": ["everyone"]}
    if m == "here":
        return "@here", {"parse": ["everyone"]}
    if m.startswith("role:"):
        role_id = mention.split(":", 1)[1].strip()
        return f"<@&{role_id}>", {"roles": [role_id]}
    return None, {"parse": []}


def build_discord_payload(event: NotifyEvent, *, mention: str = "none") -> dict[str, Any]:
    lst = event.listing
    is_drop = event.kind is EventKind.PRICE_DROP

    if is_drop:
        title = f"📉 Prijsverlaging — {event.search_name}"
        price_value = (
            f"~~€ {event.old_price_cents / 100:.2f}~~ → " f"**€ {event.new_price_cents / 100:.2f}**"
        )
    else:
        title = f"🔍 Nieuw — {event.search_name}"
        price_value = f"**{lst.price.display}**"

    description = f"**{lst.title}**"
    if lst.description:
        description += f"\n{lst.description}"
    if len(description) > 4090:
        description = description[:4087] + "..."

    fields = [{"name": "💰 Prijs", "value": price_value, "inline": True}]
    fields.append({"name": "📍 Locatie", "value": lst.location or "—", "inline": True})
    if lst.condition:
        fields.append({"name": "🏷️ Staat", "value": lst.condition, "inline": True})
    if lst.seller_name:
        verified = " ✅" if lst.seller_verified else ""
        fields.append(
            {"name": "👤 Verkoper", "value": f"{lst.seller_name}{verified}", "inline": True}
        )
    fields.append(
        {"name": "🔗 Advertentie", "value": f"[Bekijk op Marktplaats]({lst.url})", "inline": False}
    )

    embed: dict[str, Any] = {
        "title": title,
        "url": lst.url,
        "description": description,
        "color": _COLOR_DROP if is_drop else _COLOR_NEW,
        "timestamp": datetime.now(UTC).isoformat(),
        "fields": fields,
        "footer": {"text": f"Marktplaats Monitor • {event.search_name}"},
    }
    if lst.image_url:
        embed["image"] = {"url": lst.image_url}

    content, allowed = resolve_mention(mention)
    payload: dict[str, Any] = {"embeds": [embed], "allowed_mentions": allowed}
    if content:
        payload["content"] = content
    return payload


def send_discord(
    webhook_url: str,
    payload: dict[str, Any],
    *,
    session: requests.Session | None = None,
    max_retries: int = 2,
) -> bool:
    """POST a payload to a Discord webhook. Returns True on success."""
    sess = session or requests.Session()
    for attempt in range(max_retries + 1):
        try:
            resp = sess.post(webhook_url, json=payload, timeout=15)
        except requests.RequestException as e:
            logger.warning("Discord send error (attempt %d): %s", attempt + 1, e)
        else:
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 429 and attempt < max_retries:
                retry_after = resp.headers.get("Retry-After", "1")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 1.0
                logger.warning("Discord rate limited, retrying in %.1fs", delay)
                time.sleep(delay)
                continue
            logger.error("Discord send failed: HTTP %s %s", resp.status_code, resp.text[:200])
            return False
        if attempt < max_retries:
            time.sleep(1.0)
    return False
