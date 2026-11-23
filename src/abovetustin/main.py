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
from abovetustin.post.bluesky import MAX_LENGTH, BlueskyPoster
from abovetustin.post.images import ImageDirectory
from abovetustin.post.jsonl import JsonlLog, read
from abovetustin.post.template import compose
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
    run = commands.add_parser("run", help="poll the receiver, log sightings and post them")
    run.add_argument("--config", type=Path, default=config_module.DEFAULT_PATH)
    run.add_argument("--dry-run", action="store_true", help="log and render, do not post anywhere")
    run.add_argument("-v", "--verbose", action="store_true")
    show = commands.add_parser("compose", help="print the post text for logged sightings")
    show.add_argument("--config", type=Path, default=config_module.DEFAULT_PATH)
    show.add_argument("--last", type=int, default=10, metavar="N", help="how many, newest last")
    show.add_argument("-v", "--verbose", action="store_true")
    check = commands.add_parser(
        "check", help="verify the config, the receiver and the Bluesky login, then exit"
    )
    check.add_argument("--config", type=Path, default=config_module.DEFAULT_PATH)
    check.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    # The atproto SDK's HTTP client logs every request at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        cfg = config_module.load(args.config)
    except config_module.ConfigError as exc:
        parser.exit(2, f"error: {exc}\n")

    if args.command == "compose":
        return _compose(cfg, args.last)
    if args.command == "check":
        return _check(cfg)

    sinks: list[Sink] = [JsonlLog(cfg.log_path).post, ImageDirectory(cfg.image_dir).post]
    if args.dry_run:
        mode = "dry run, posting nowhere"
    elif cfg.bluesky is None:
        parser.exit(2, "error: no [bluesky] section in the config; add one or run with --dry-run\n")
    else:
        poster = BlueskyPoster(cfg.bluesky, cfg.post)
        try:
            poster.login()
        except Exception as exc:
            parser.exit(2, f"error: Bluesky login as {cfg.bluesky.handle} failed: {exc}\n")
        sinks.append(poster.post)
        mode = f"posting to Bluesky as {cfg.bluesky.handle}"

    tracker = Tracker(cfg.tracker)
    log.info(
        "%s: polling %s every %s s, logging sightings to %s, images to %s",
        mode,
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


def _check(cfg: config_module.Config) -> int:
    """Fail fast on anything the service would fail on: an unreachable receiver
    or a bad Bluesky login. Exit status 0 means run will start cleanly."""
    try:
        snapshot = readsb.fetch(cfg.source.url, cfg.receiver, cfg.source.timeout_s)
    except Exception as exc:
        log.error("receiver: cannot read %s: %s", cfg.source.url, exc)
        return 1
    log.info("receiver: %d aircraft with positions at %s", len(snapshot.aircraft), cfg.source.url)
    if cfg.bluesky is None:
        log.info("bluesky: not configured; run would need --dry-run")
    else:
        try:
            BlueskyPoster(cfg.bluesky, cfg.post).login()
        except Exception as exc:
            log.error("bluesky: login as %s failed: %s", cfg.bluesky.handle, exc)
            return 1
    log.info(
        "config ok: alarm zone %.1f km / %.0f°, %d post rules, rendering %s",
        cfg.tracker.distance_alarm_m / 1000,
        cfg.tracker.elevation_alarm_deg,
        len(cfg.post.rules),
        "on" if cfg.render else "off",
    )
    return 0


def _compose(cfg: config_module.Config, last: int) -> int:
    """Print what the last few logged sightings would post as, for tuning
    the template and rules without posting."""
    if not cfg.log_path.exists():
        print(f"no sighting log at {cfg.log_path}", file=sys.stderr)
        return 1
    records = list(read(cfg.log_path))[-last:]
    for sighting, image_name in records:
        text = compose(sighting, cfg.post, MAX_LENGTH)
        print(f"{text}\n    [{len(text)} chars, image: {image_name or 'none'}]")
    return 0


def _render_or_none(renderer: Tar1090Renderer, sighting: Sighting) -> bytes | None:
    closest = sighting.closest
    try:
        return renderer.render(closest.hex, (closest.lat_deg, closest.lon_deg))
    except RenderError as exc:
        log.warning("no image for %s: %s", sighting.closest.ident, exc)
        return None
