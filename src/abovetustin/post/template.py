"""Compose the text of a post from a sighting.

Boundary module: this is where metres become the miles and feet the posts
have always used.

The base template uses ``${name}`` placeholders from :data:`VARIABLES`, the
same set v1 offered. Rules add hashtags and can swap in a different
template, each gated by conditions on the sighting; see :class:`Rule`.
Rules are evaluated in order, all conditions of a rule must hold, the
first matching rule with a template wins, and tags are appended while the
post stays within the poster's length limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, tzinfo
from string import Template

from abovetustin import geomath, units
from abovetustin.tracker import Sighting
from abovetustin.units import Magnitude

#: Placeholders a template may use, with what each one renders.
VARIABLES = {
    "flight": "callsign, else registration, else the address",
    "icao": "the 24-bit address, upper case",
    "registration": "registration, if known",
    "type": "ICAO type designator, if known",
    "dist_mi": "closest-approach distance, statute miles",
    "dist_km": "closest-approach distance, kilometres",
    "dist_nm": "closest-approach distance, nautical miles",
    "alt_ft": "altitude at closest approach, feet",
    "alt_m": "altitude at closest approach, metres",
    "el": "elevation above the horizon at closest approach, degrees",
    "az": "bearing from the receiver at closest approach, degrees",
    "heading": "compass point the aircraft was heading, e.g. SW",
    "track": "track at closest approach, degrees",
    "speed_mph": "ground speed, miles per hour",
    "speed_kmph": "ground speed, kilometres per hour",
    "speed_kts": "ground speed, knots",
    "vert_rate_ftpm": "vertical rate, feet per minute",
    "vert_rate_mpm": "vertical rate, metres per minute",
    "squawk": "squawk code",
    "rssi": "signal strength at closest approach, dB",
    "time": "local time at closest approach, HH:MM:SS",
    "date": "local date at closest approach, YYYY-MM-DD",
}

UNKNOWN = "?"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class TemplateError(ValueError):
    pass


def validate_template(text: str) -> None:
    """Raise :class:`TemplateError` if ``text`` uses an unknown placeholder
    or is malformed."""
    try:
        names = {m.group("named") or m.group("braced") for m in Template.pattern.finditer(text)}
    except Exception as exc:  # pragma: no cover - Template.pattern is permissive
        raise TemplateError(str(exc)) from exc
    names.discard(None)
    unknown = sorted(n for n in names if n not in VARIABLES)
    if unknown:
        raise TemplateError(f"unknown template variable(s): {', '.join(unknown)}")
    try:
        Template(text).substitute(dict.fromkeys(VARIABLES, ""))
    except ValueError as exc:
        raise TemplateError(f"malformed template: {exc}") from exc


@dataclass(frozen=True, slots=True)
class Rule:
    """A hashtag and/or replacement template, applied when every set
    condition holds. Ranges are inclusive. Headings and hours may wrap:
    ``heading_min_deg=315, heading_max_deg=45`` is the northern quadrant."""

    tag: str | None = None
    template: str | None = None
    altitude_min_m: float | None = None
    altitude_max_m: float | None = None
    distance_min_m: float | None = None
    distance_max_m: float | None = None
    speed_min_m_per_s: float | None = None
    speed_max_m_per_s: float | None = None
    vertical_rate_min_m_per_s: float | None = None
    vertical_rate_max_m_per_s: float | None = None
    elevation_min_deg: float | None = None
    elevation_max_deg: float | None = None
    heading_min_deg: float | None = None
    heading_max_deg: float | None = None
    #: Local-time window, inclusive start, exclusive end; may cross midnight.
    hours: tuple[time, time] | None = None
    weekdays: frozenset[str] = frozenset()
    anonymous: bool | None = None
    on_ground: bool | None = None

    def matches(self, sighting: Sighting, local_time: datetime) -> bool:
        a = sighting.closest
        checks = (
            _within(a.altitude_m, self.altitude_min_m, self.altitude_max_m),
            _within(a.distance_m, self.distance_min_m, self.distance_max_m),
            _within(a.ground_speed_m_per_s, self.speed_min_m_per_s, self.speed_max_m_per_s),
            _within(
                a.vertical_rate_m_per_s,
                self.vertical_rate_min_m_per_s,
                self.vertical_rate_max_m_per_s,
            ),
            _within(a.elevation_deg, self.elevation_min_deg, self.elevation_max_deg),
            _heading_within(a.track_deg, self.heading_min_deg, self.heading_max_deg),
            _hours_within(local_time.time(), self.hours),
            not self.weekdays or WEEKDAYS[local_time.weekday()] in self.weekdays,
            self.anonymous is None or a.is_anonymous == self.anonymous,
            self.on_ground is None or a.on_ground == self.on_ground,
        )
        return all(checks)


@dataclass(frozen=True, slots=True)
class PostConfig:
    template: str
    #: Appended to every post, after any rule tags, while there is room.
    hashtags: tuple[str, ...] = ()
    rules: tuple[Rule, ...] = ()
    #: Clock for ${time}, ${date} and the hours/weekdays conditions.
    tz: tzinfo | None = None


def variables(sighting: Sighting, tz: tzinfo | None = None) -> dict[str, str]:
    """Every template variable rendered as text, ``?`` where unknown."""
    a = sighting.closest
    q = units.Quantity
    local = a.observed_at.astimezone(tz)

    def conv(value_si: Magnitude | None, si_unit: str, target: str, fmt: str) -> str:
        if value_si is None:
            return UNKNOWN
        return format(q(value_si, si_unit).to(target).magnitude, fmt)

    def num(value: Magnitude | None, fmt: str) -> str:
        return UNKNOWN if value is None else format(value, fmt)

    return {
        "flight": a.ident,
        "icao": a.hex.upper(),
        "registration": a.registration or UNKNOWN,
        "type": a.aircraft_type or UNKNOWN,
        "dist_mi": conv(a.distance_m, "m", "mi", ".1f"),
        "dist_km": conv(a.distance_m, "m", "km", ".1f"),
        "dist_nm": conv(a.distance_m, "m", "nmi", ".1f"),
        "alt_ft": conv(a.altitude_m, "m", "ft", ".0f"),
        "alt_m": conv(a.altitude_m, "m", "m", ".0f"),
        "el": num(a.elevation_deg, ".1f"),
        "az": num(a.bearing_deg, ".0f"),
        "heading": geomath.compass_point(a.track_deg),
        "track": num(a.track_deg, ".0f"),
        "speed_mph": conv(a.ground_speed_m_per_s, "m/s", "mph", ".0f"),
        "speed_kmph": conv(a.ground_speed_m_per_s, "m/s", "km/h", ".0f"),
        "speed_kts": conv(a.ground_speed_m_per_s, "m/s", "knot", ".0f"),
        "vert_rate_ftpm": conv(a.vertical_rate_m_per_s, "m/s", "ft/min", "+.0f"),
        "vert_rate_mpm": conv(a.vertical_rate_m_per_s, "m/s", "m/min", "+.0f"),
        "squawk": a.squawk or UNKNOWN,
        "rssi": num(a.rssi_db, ".1f"),
        "time": local.strftime("%H:%M:%S"),
        "date": local.strftime("%Y-%m-%d"),
    }


def compose(sighting: Sighting, config: PostConfig, max_length: int) -> str:
    """The post text: the (possibly rule-chosen) template filled in, then
    rule tags and the standing hashtags appended while they fit."""
    local = sighting.closest.observed_at.astimezone(config.tz)
    matched = [rule for rule in config.rules if rule.matches(sighting, local)]
    template = next((r.template for r in matched if r.template), config.template)
    text = Template(template).substitute(variables(sighting, config.tz))
    for tag in [r.tag for r in matched if r.tag] + list(config.hashtags):
        if tag in text.split():
            continue
        if len(text) + 1 + len(tag) <= max_length:
            text += " " + tag
    return text


def _within(value: Magnitude | None, low: Magnitude | None, high: Magnitude | None) -> bool:
    if low is None and high is None:
        return True
    if value is None:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def _heading_within(value_deg: float | None, low_deg: float | None, high_deg: float | None) -> bool:
    if low_deg is None and high_deg is None:
        return True
    if value_deg is None:
        return False
    value_deg %= 360
    low_deg = 0.0 if low_deg is None else low_deg % 360
    high_deg = 360.0 if high_deg is None else high_deg % 360
    if low_deg <= high_deg:
        return low_deg <= value_deg <= high_deg
    return value_deg >= low_deg or value_deg <= high_deg  # wraps through north


def _hours_within(value: time, window: tuple[time, time] | None) -> bool:
    if window is None:
        return True
    start, end = window
    if start <= end:
        return start <= value < end
    return value >= start or value < end  # crosses midnight
