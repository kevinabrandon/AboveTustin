"""Keep every rendered map image in a directory."""

from __future__ import annotations

from pathlib import Path

from abovetustin.post import Post


class ImageDirectory:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def post(self, post: Post) -> None:
        if post.image_png is None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / post.image_name).write_bytes(post.image_png)
