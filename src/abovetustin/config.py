"""Configuration from a TOML file kept outside the repository.

Boundary module: values with units are written as strings with units
(``"1.2 mi"``, ``"30 s"``) and become SI floats here. Angles are plain
numbers in degrees, the one exception to that rule.

See ``config.example.toml`` at the repository root for every key.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from abovetustin import units
from abovetustin.geomath import LatLonDeg
from abovetustin.post.bluesky import BlueskyConfig
from abovetustin.post.template import PostConfig, Rule, TemplateError, validate_template
from abovetustin.render.tar1090 import CENTER_MODES, RenderConfig
from abovetustin.tracker import TrackerConfig

DEFAULT_PATH = Path("~/.config/abovetustin/config.toml")
DEFAULT_LOG_PATH = Path("~/.local/share/abovetustin/sightings.jsonl")
DEFAULT_SOURCE_URL = "http://localhost/tar1090/data/aircraft.json"
DEFAULT_RENDER_URL = "http://localhost/tar1090/"
DEFAULT_IMAGE_DIR = Path("~/.local/share/abovetustin/images")
#: The v1 tweet template.
DEFAULT_TEMPLATE = (
    "#${flight} : ${dist_mi} mi away @ ${alt_ft} ft and ${el}° frm hrzn, "
    "heading ${heading} @ ${speed_mph}mi/h ${time}."
)

#: Rule keys, how each is parsed, and the Rule field it sets.
_RULE_QUANTITIES = {
    "altitude_min": ("m", "altitude_min_m"),
    "altitude_max": ("m", "altitude_max_m"),
    "distance_min": ("m", "distance_min_m"),
    "distance_max": ("m", "distance_max_m"),
    "speed_min": ("m/s", "speed_min_m_per_s"),
    "speed_max": ("m/s", "speed_max_m_per_s"),
    "vertical_rate_min": ("m/s", "vertical_rate_min_m_per_s"),
    "vertical_rate_max": ("m/s", "vertical_rate_max_m_per_s"),
}
_RULE_ANGLES = ("elevation_min_deg", "elevation_max_deg", "heading_min_deg", "heading_max_deg")
_RULE_FLAGS = ("anonymous", "on_ground")
_RULE_KEYS = (
    {"tag", "template", "hours", "weekdays"}
    | set(_RULE_QUANTITIES)
    | set(_RULE_ANGLES)
    | set(_RULE_FLAGS)
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SourceConfig:
    url: str
    poll_interval_s: float
    timeout_s: float


@dataclass(frozen=True, slots=True)
class Config:
    receiver: LatLonDeg
    source: SourceConfig
    tracker: TrackerConfig
    #: Every sighting is appended here as one JSON line, posted or not.
    log_path: Path
    #: None when map images are disabled.
    render: RenderConfig | None
    #: Where rendered images are kept.
    image_dir: Path
    post: PostConfig
    #: None when no Bluesky account is configured; the bot then only logs.
    bluesky: BlueskyConfig | None


def load(path: Path = DEFAULT_PATH) -> Config:
    path = path.expanduser()
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise ConfigError(f"no config file at {path}; copy config.example.toml there") from None
    return parse(text)


def parse(text: str) -> Config:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config is not valid TOML: {exc}") from None

    receiver = _Section(data, "receiver")
    source = _Section(data, "source", required=False)
    tracker = _Section(data, "tracker")
    log = _Section(data, "log", required=False)
    render = _Section(data, "render", required=False)
    post = _Section(data, "post", required=False)
    bluesky = _Section(data, "bluesky", required=False)

    return Config(
        receiver=(receiver.number("latitude_deg"), receiver.number("longitude_deg")),
        source=SourceConfig(
            url=source.string("url", DEFAULT_SOURCE_URL),
            poll_interval_s=source.quantity("poll_interval", "s", "1 s"),
            timeout_s=source.quantity("timeout", "s", "10 s"),
        ),
        tracker=TrackerConfig(
            distance_alarm_m=tracker.quantity("distance_alarm", "m"),
            elevation_alarm_deg=tracker.number("elevation_alarm_deg"),
            wait_updates=tracker.integer("wait_updates", 4),
            max_position_age_s=tracker.quantity("max_position_age", "s", "30 s"),
        ),
        log_path=Path(log.string("path", str(DEFAULT_LOG_PATH))).expanduser(),
        render=(
            RenderConfig(
                url=render.string("url", DEFAULT_RENDER_URL),
                zoom=render.integer("zoom", 11),
                width_px=render.integer("width_px", 1280),
                height_px=render.integer("height_px", 720),
                center=render.choice("center", CENTER_MODES, "grid"),
                grid_deg=render.number("grid_deg", 0.1),
                show_receiver=render.boolean("show_receiver", False),
                ring_distances_m=tuple(
                    render.quantities("ring_distances", "m", ["1 mi", "2 mi", "5 mi"])
                ),
                browser_channel=render.string("browser_channel", "chrome"),
                reload_after_s=render.quantity("reload_after", "s", "1 h"),
            )
            if render.boolean("enabled", True)
            else None
        ),
        image_dir=Path(render.string("image_dir", str(DEFAULT_IMAGE_DIR))).expanduser(),
        post=PostConfig(
            template=post.template("template", DEFAULT_TEMPLATE),
            hashtags=tuple(post.strings("hashtags", [])),
            rules=tuple(_rule(post, i, raw) for i, raw in enumerate(post.tables("rules"))),
            tz=post.timezone("timezone"),
        ),
        bluesky=(
            BlueskyConfig(
                handle=bluesky.string("handle"),
                app_password=bluesky.string("app_password"),
                service=bluesky.string("service", "https://bsky.social"),
            )
            if bluesky.table
            else None
        ),
    )


def _rule(post: _Section, index: int, raw: Any) -> Rule:
    section = _Section({"rule": raw}, "rule")
    section.name = f"post.rules[{index}]"
    unknown = sorted(set(section.table) - _RULE_KEYS)
    if unknown:
        raise ConfigError(f"[{section.name}] unknown key(s): {', '.join(unknown)}")
    if "tag" not in section.table and "template" not in section.table:
        raise ConfigError(f"[{section.name}] needs a tag or a template")
    fields: dict[str, Any] = {}
    if "tag" in section.table:
        fields["tag"] = section.string("tag")
    if "template" in section.table:
        fields["template"] = section.template("template")
    for key, (like, field) in _RULE_QUANTITIES.items():
        if key in section.table:
            fields[field] = section.quantity(key, like)
    for key in _RULE_ANGLES:
        if key in section.table:
            fields[key] = section.number(key)
    for key in _RULE_FLAGS:
        if key in section.table:
            fields[key] = section.boolean(key, False)
    if "hours" in section.table:
        fields["hours"] = section.hours("hours")
    if "weekdays" in section.table:
        days = [d.lower()[:3] for d in section.strings("weekdays")]
        bad = [d for d in days if d not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
        if bad:
            raise ConfigError(f"[{section.name}] weekdays: unknown day(s) {', '.join(bad)}")
        fields["weekdays"] = frozenset(days)
    return Rule(**fields)


class _Section:
    """One TOML table with typed, well-complained-about accessors."""

    def __init__(self, data: dict[str, Any], name: str, required: bool = True) -> None:
        self.name = name
        table = data.get(name)
        if table is None:
            if required:
                raise ConfigError(f"missing [{name}] section")
            table = {}
        if not isinstance(table, dict):
            raise ConfigError(f"[{name}] must be a table")
        self.table: dict[str, Any] = table

    def _get(self, key: str, default: Any) -> Any:
        if key in self.table:
            return self.table[key]
        if default is None:
            raise ConfigError(f"[{self.name}] is missing {key}")
        return default

    def string(self, key: str, default: str | None = None) -> str:
        value = self._get(key, default)
        if not isinstance(value, str):
            raise ConfigError(f"[{self.name}] {key} must be a string")
        return value

    def choice(self, key: str, choices: tuple[str, ...], default: str) -> str:
        value = self.string(key, default)
        if value not in choices:
            raise ConfigError(f"[{self.name}] {key} must be one of {', '.join(choices)}")
        return value

    def quantities(self, key: str, like: str, default: list[str]) -> list[float]:
        """A list of strings with units, each returned as an SI magnitude."""
        values = self._get(key, default)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ConfigError(
                f'[{self.name}] {key} must be a list of strings with units, like ["1 mi"]'
            )
        out = []
        for value in values:
            try:
                out.append(units.parse(value, like))
            except Exception as exc:
                raise self._not_a_quantity(key, value, like, exc) from None
        return out

    def _not_a_quantity(self, key: str, value: str, like: str, exc: Exception) -> ConfigError:
        return ConfigError(
            f"[{self.name}] {key}: {value!r} is not a quantity compatible with {like!r} ({exc})"
        )

    def strings(self, key: str, default: list[str] | None = None) -> list[str]:
        values = self._get(key, default)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ConfigError(f"[{self.name}] {key} must be a list of strings")
        return values

    def tables(self, key: str) -> list[dict[str, Any]]:
        values = self.table.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, dict) for v in values):
            raise ConfigError(
                f"[{self.name}] {key} must be an array of tables ([[{self.name}.{key}]])"
            )
        return values

    def template(self, key: str, default: str | None = None) -> str:
        text = self.string(key, default)
        try:
            validate_template(text)
        except TemplateError as exc:
            raise ConfigError(f"[{self.name}] {key}: {exc}") from None
        return text

    def timezone(self, key: str) -> ZoneInfo | None:
        """An IANA zone name, or None (the system's local time) when absent."""
        if key not in self.table:
            return None
        name = self.string(key)
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigError(f"[{self.name}] {key}: unknown time zone {name!r}") from None

    def hours(self, key: str) -> tuple[time, time]:
        """A local-time window like "23:00-07:00"."""
        text = self.string(key)
        try:
            start, end = (time.fromisoformat(part.strip()) for part in text.split("-"))
        except ValueError:
            raise ConfigError(f'[{self.name}] {key} must look like "23:00-07:00"') from None
        return (start, end)

    def boolean(self, key: str, default: bool) -> bool:
        value = self._get(key, default)
        if not isinstance(value, bool):
            raise ConfigError(f"[{self.name}] {key} must be true or false")
        return value

    def number(self, key: str, default_deg: float | None = None) -> float:
        """A plain number. The only unit-bearing plain numbers in the config are
        angles in degrees, hence the name of the default."""
        value = self._get(key, default_deg)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"[{self.name}] {key} must be a number")
        return float(value)

    def integer(self, key: str, default: int | None = None) -> int:
        value = self._get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"[{self.name}] {key} must be a whole number")
        return value

    def quantity(self, key: str, like: str, default: str | None = None) -> float:
        """A string with units, returned as an SI magnitude."""
        value = self._get(key, default)
        if not isinstance(value, str):
            raise ConfigError(
                f'[{self.name}] {key} must be a string with units, like "{default or like}"'
            )
        try:
            return units.parse(value, like)
        except Exception as exc:  # DimensionalityError, UndefinedUnitError, parse errors
            raise self._not_a_quantity(key, value, like, exc) from None
