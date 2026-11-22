"""Configuration from a TOML file kept outside the repository.

Boundary module: values with units are written as strings with units
(``"1.2 mi"``, ``"30 s"``) and become SI floats here. Angles are plain
numbers in degrees, the one exception to that rule.

See ``config.example.toml`` at the repository root for every key.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from abovetustin import units
from abovetustin.geomath import LatLonDeg
from abovetustin.tracker import TrackerConfig

DEFAULT_PATH = Path("~/.config/abovetustin/config.toml")
DEFAULT_LOG_PATH = Path("~/.local/share/abovetustin/sightings.jsonl")
DEFAULT_SOURCE_URL = "http://localhost/tar1090/data/aircraft.json"


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
    )


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

    def number(self, key: str) -> float:
        value = self._get(key, None)
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
            raise ConfigError(
                f"[{self.name}] {key}: {value!r} is not a quantity compatible with {like!r} ({exc})"
            ) from None
