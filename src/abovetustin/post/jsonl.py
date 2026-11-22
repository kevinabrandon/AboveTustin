"""Append every sighting to a JSON Lines file.

Always on, whether or not anything is posted. The record is the internal
representation (SI units, suffixed keys) so it can be replayed into later
versions of the templates or the tracker without loss.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from abovetustin.aircraft import Aircraft
from abovetustin.post import Post
from abovetustin.tracker import Sighting

SCHEMA_VERSION = 1


def record(sighting: Sighting, image_name: str | None = None) -> dict[str, Any]:
    """The JSON-ready form of a sighting."""
    closest = asdict(sighting.closest)
    closest["observed_at"] = sighting.closest.observed_at.isoformat()
    return {
        "schema": SCHEMA_VERSION,
        "first_seen_at": sighting.first_seen_at.isoformat(),
        "last_seen_at": sighting.last_seen_at.isoformat(),
        "samples": sighting.samples,
        "image": image_name,
        "closest": closest,
    }


def from_record(record: dict[str, Any]) -> Sighting:
    """Inverse of :func:`record`."""
    closest = dict(record["closest"])
    closest["observed_at"] = datetime.fromisoformat(closest["observed_at"])
    return Sighting(
        closest=Aircraft(**closest),
        first_seen_at=datetime.fromisoformat(record["first_seen_at"]),
        last_seen_at=datetime.fromisoformat(record["last_seen_at"]),
        samples=int(record["samples"]),
    )


def read(path: Path) -> Iterator[tuple[Sighting, str | None]]:
    """Every sighting in a log file, oldest first, with its image name."""
    with path.open() as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                yield from_record(rec), rec.get("image")


class JsonlLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def post(self, post: Post) -> None:
        image_name = post.image_name if post.image_png is not None else None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(record(post.sighting, image_name), separators=(",", ":")) + "\n")
