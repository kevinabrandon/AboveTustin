"""Post sightings to Bluesky through the atproto SDK.

Hashtags in the composed text become tag facets so they are clickable.
The map image, when there is one, is attached with the plain-language
summary as its alt text.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from abovetustin.post import Post
from abovetustin.post.template import PostConfig, compose
from abovetustin.post.text import summary

log = logging.getLogger(__name__)

#: Bluesky's limit is 300 graphemes. Posts here are ASCII plus the odd
#: degree sign, for which code points are the same count.
MAX_LENGTH = 300

_TOKENS = re.compile(r"\s+|\S+")
# A word after the #, not all digits: "#2CloseForComfort" is a tag, "#2" is not.
_HASHTAG = re.compile(r"^#(?!\d+$)(\w+)$")


@dataclass(frozen=True, slots=True)
class BlueskyConfig:
    handle: str
    app_password: str
    service: str = "https://bsky.social"


def rich_text(text: str) -> Any:
    """An atproto TextBuilder for ``text`` with every ``#hashtag`` as a tag facet."""
    from atproto import client_utils

    builder = client_utils.TextBuilder()
    for token in _TOKENS.findall(text):
        m = _HASHTAG.match(token)
        if m:
            builder.tag(token, m.group(1))
        else:
            builder.text(token)
    return builder


class BlueskyPoster:
    def __init__(
        self,
        config: BlueskyConfig,
        post_config: PostConfig,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.config = config
        self.post_config = post_config
        self._client_factory = client_factory or _default_client
        self._client: Any = None

    def login(self) -> str:
        """Authenticate; returns the account's DID. Raises on bad credentials."""
        self._client = self._client_factory(self.config.service)
        profile = self._client.login(self.config.handle, self.config.app_password)
        did = getattr(profile, "did", None) or self.config.handle
        log.info("logged in to Bluesky as %s", self.config.handle)
        return did

    def post(self, post: Post) -> None:
        if self._client is None:
            self.login()
        text = compose(post.sighting, self.post_config, MAX_LENGTH)
        body = rich_text(text)
        if post.image_png is not None:
            alt = summary(post.sighting, self.post_config.tz)
            self._client.send_image(text=body, image=post.image_png, image_alt=alt)
        else:
            self._client.send_post(body)
        log.info("posted to Bluesky: %s", text)


def _default_client(service: str) -> Any:
    from atproto import Client

    return Client(service)
