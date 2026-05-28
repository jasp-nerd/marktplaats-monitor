"""Apprise adapter — the default, multi-service notification backend.

Apprise supports ~100 services out of the box; the developer does **not**
allowlist anything. The user just supplies Apprise URLs (and optional tags) in
their config / env, and this sends to all of them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

import apprise

from marktplaats_monitor.notify.discord_embed import resolve_mention

logger = logging.getLogger(__name__)

UrlSpec = tuple[str, list[str]]  # (apprise_url, tags)


class AppriseSink:
    """Wraps an :class:`apprise.Apprise` instance built from user URLs."""

    def __init__(
        self,
        url_specs: Iterable[UrlSpec],
        *,
        app_name: str = "Marktplaats Monitor",
        apprise_factory: Callable[[], object] | None = None,
    ) -> None:
        self._ap = (apprise_factory or apprise.Apprise)()
        self._count = 0
        for url, tags in url_specs:
            if not url:
                continue
            if self._ap.add(url, tag=tags or None):
                self._count += 1
            else:
                logger.error("Apprise rejected URL (check the scheme/credentials): %r", url)
        self.app_name = app_name

    @property
    def has_targets(self) -> bool:
        return self._count > 0

    def notify(
        self,
        title: str,
        body: str,
        *,
        tag: str | list[str] | None = None,
        attach: str | None = None,
        mention: str = "none",
    ) -> bool:
        """Send through every matching Apprise URL. Returns True on success.

        ``mention`` (none|everyone|here|role:<id>) is prepended to the body as
        a literal token — Discord renders it as a real ping, and it is
        harmless/visible on other services.
        """
        content, _ = resolve_mention(mention)
        if content:
            body = f"{content}\n{body}"
        ok = self._ap.notify(
            title=title,
            body=body,
            tag=tag,
            attach=attach or None,
            body_format="markdown",
        )
        # apprise returns True/False, or None when no URL matched the tag.
        if ok is False:
            logger.error("Apprise failed to deliver (tag=%s)", tag)
        return bool(ok)
