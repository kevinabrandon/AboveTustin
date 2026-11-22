"""The poll loop and the ``abovetustin`` command."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from abovetustin import config as config_module
from abovetustin.post import Post
from abovetustin.post.images import ImageDirectory
from abovetustin.post.jsonl import JsonlLog
from abovetustin.post.text import summary
from abovetustin.render.tar1090 import RenderError, Tar1090Renderer
from abovetustin.source import readsb
from abovetustin.tracker import Sighting, Tracker

log = logging.getLogger("abovetustin")

#: Anything that accepts a completed post: the JSONL log, the image directory, a social poster.
Sink = Callable[[Post], None]
#: Produces the map image for a sighting, or None if it cannot.
Render = Callable[[Sighting], bytes | None]


def poll_loop(
    fetch: Callable[[], readsb.Snapshot],
    tracker: Tracker,
    sinks: Sequence[Sink],
    interval_s: float,
    *,
    render: Render | None = None,
    when_idle: Callable[[], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_polls: int | None = None,
) -> int:
    """Poll ``fetch`` every ``interval_s``, feed the tracker, render an image
    for each completed sighting and hand the post to every sink. Returns the
    number of sightings. A failing fetch is logged and skipped; a failing sink
    is logged and the others still run. ``when_idle`` runs on polls where
    nothing is being tracked, for housekeeping that would disturb a track.
    """
    sightings = 0
    polls = 0
    last_observed_at = None
    while max_polls is None or polls < max_polls:
        polls += 1
        try:
            snapshot = fetch()
        except Exception as exc:
            log.warning("fetch failed: %s", exc)
            sleep(interval_s)
            continue

        if snapshot.observed_at != last_observed_at:
            last_observed_at = snapshot.observed_at
            tracked_before = {s.closest.hex for s in tracker.in_progress()}
            completed = tracker.update(snapshot.aircraft)
            for provisional in tracker.in_progress():
                if provisional.closest.hex not in tracked_before:
                    log.info("tracking %s", summary(provisional))
            for sighting in completed:
                sightings += 1
                log.info("sighting %s", summary(sighting))
                post = Post(sighting, render(sighting) if render is not None else None)
                for sink in sinks:
                    try:
                        sink(post)
                    except Exception:
                        log.exception("sink %r failed", sink)
            if when_idle is not None and not tracker.in_progress():
                when_idle()
        sleep(interval_s)
    return sightings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abovetustin")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="poll the receiver and log sightings")
    run.add_argument("--config", type=Path, default=config_module.DEFAULT_PATH)
    run.add_argument("--dry-run", action="store_true", help="log sightings, do not post anywhere")
    run.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    try:
        cfg = config_module.load(args.config)
    except config_module.ConfigError as exc:
        parser.exit(2, f"error: {exc}\n")
    if not args.dry_run:
        parser.exit(2, "error: no posting backends exist yet; run with --dry-run\n")

    tracker = Tracker(cfg.tracker)
    sinks: list[Sink] = [JsonlLog(cfg.log_path).post, ImageDirectory(cfg.image_dir).post]
    log.info(
        "dry run: polling %s every %s s, logging sightings to %s, images to %s",
        cfg.source.url,
        cfg.source.poll_interval_s,
        cfg.log_path,
        cfg.image_dir if cfg.render else "nowhere (rendering disabled)",
    )

    def fetch() -> readsb.Snapshot:
        return readsb.fetch(cfg.source.url, cfg.receiver, cfg.source.timeout_s)

    try:
        if cfg.render is None:
            poll_loop(fetch, tracker, sinks, cfg.source.poll_interval_s)
        else:
            with Tar1090Renderer(cfg.render, cfg.receiver) as renderer:
                poll_loop(
                    fetch,
                    tracker,
                    sinks,
                    cfg.source.poll_interval_s,
                    render=lambda s: _render_or_none(renderer, s),
                    when_idle=renderer.reload_if_stale,
                )
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


def _render_or_none(renderer: Tar1090Renderer, sighting: Sighting) -> bytes | None:
    try:
        return renderer.render(sighting.closest.hex)
    except RenderError as exc:
        log.warning("no image for %s: %s", sighting.closest.ident, exc)
        return None
