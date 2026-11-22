"""Where sightings go: a local log, an image directory, and the social accounts."""

from __future__ import annotations

from dataclasses import dataclass

from abovetustin.tracker import Sighting


@dataclass(frozen=True, slots=True)
class Post:
    """A completed sighting and its map image, if one was rendered."""

    sighting: Sighting
    image_png: bytes | None = None

    @property
    def image_name(self) -> str:
        """File name for the image, the same wherever it is written or referenced."""
        closest = self.sighting.closest
        return f"{closest.observed_at:%Y%m%dT%H%M%SZ}_{closest.hex.lstrip('~')}.png"
