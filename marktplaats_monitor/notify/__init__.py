"""Notification facade.

``Notifier`` is the single entry point the monitor uses. Per event it routes
to the Apprise backend (default) or the opt-in native Discord renderer.
"""

from __future__ import annotations

import logging

import requests

from marktplaats_monitor.models import NotifyEvent
from marktplaats_monitor.notify.apprise_sink import AppriseSink
from marktplaats_monitor.notify.discord_embed import (
    build_discord_payload,
    resolve_mention,
    send_discord,
)
from marktplaats_monitor.notify.render import build_body, build_title

logger = logging.getLogger(__name__)

__all__ = ["Notifier"]


class Notifier:
    """Routes notifications to Apprise or native Discord."""

    def __init__(
        self,
        *,
        apprise_sink: AppriseSink | None = None,
        discord_webhook: str | None = None,
        listings_tag: str | list[str] = "listings",
        errors_tag: str | list[str] = "errors",
        session: requests.Session | None = None,
    ) -> None:
        self.apprise = apprise_sink
        self.discord_webhook = discord_webhook
        self.listings_tag = listings_tag
        self.errors_tag = errors_tag
        self._session = session or requests.Session()

    # -- listing / price-drop events --------------------------------------

    def send_event(
        self,
        event: NotifyEvent,
        *,
        backend: str = "apprise",
        mention: str = "none",
        attach_image: bool = True,
    ) -> bool:
        if backend == "discord_native":
            if not self.discord_webhook:
                logger.error("discord_native backend selected but no DISCORD_WEBHOOK_URL set")
                return False
            payload = build_discord_payload(event, mention=mention)
            return send_discord(self.discord_webhook, payload, session=self._session)

        if not self.apprise or not self.apprise.has_targets:
            logger.error("apprise backend selected but no usable Apprise URLs configured")
            return False
        attach = event.listing.image_url if attach_image else None
        return self.apprise.notify(
            build_title(event),
            build_body(event),
            tag=self.listings_tag,
            attach=attach or None,
            mention=mention,
        )

    # -- system messages (startup / errors / test) ------------------------

    def send_message(
        self,
        title: str,
        body: str,
        *,
        backend: str = "apprise",
        mention: str = "none",
        to_errors: bool = False,
    ) -> bool:
        tag = self.errors_tag if to_errors else self.listings_tag
        if backend == "discord_native":
            if not self.discord_webhook:
                logger.error("discord_native backend selected but no DISCORD_WEBHOOK_URL set")
                return False
            content, allowed = resolve_mention(mention)
            text = f"**{title}**\n{body}"
            payload = {
                "content": f"{content}\n{text}" if content else text,
                "allowed_mentions": allowed,
            }
            return send_discord(self.discord_webhook, payload, session=self._session)

        if not self.apprise or not self.apprise.has_targets:
            logger.error("apprise backend selected but no usable Apprise URLs configured")
            return False
        return self.apprise.notify(title, body, tag=tag, mention=mention)
