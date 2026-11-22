"""Aircraft from readsb's ``aircraft.json``.

Boundary module: readsb reports feet, knots and feet per minute, and this is
where they become metres and metres per second. Field names follow the
readsb JSON documentation (``alt_baro``, ``gs``, ``baro_rate``, ``seen_pos``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.request import urlopen

from abovetustin import geomath, units
from abovetustin.aircraft import Aircraft
from abovetustin.geomath import LatLonDeg


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything the receiver knew at one instant."""

    observed_at: datetime
    #: Total messages decoded since readsb started.
    messages: int
    #: Only aircraft with a position; the rest cannot be placed.
    aircraft: tuple[Aircraft, ...]


def fetch(url: str, receiver: LatLonDeg, timeout_s: float = 10.0) -> Snapshot:
    """Download and parse ``aircraft.json`` from ``url``."""
    with urlopen(url, timeout=timeout_s) as response:
        return parse(json.load(response), receiver)


def parse(data: dict[str, Any], receiver: LatLonDeg) -> Snapshot:
    """Parse a decoded ``aircraft.json`` document."""
    observed_at = datetime.fromtimestamp(float(data["now"]), tz=UTC)
    aircraft = tuple(
        sample
        for sample in (
            _aircraft(entry, receiver, observed_at) for entry in data.get("aircraft", [])
        )
        if sample is not None
    )
    return Snapshot(observed_at, int(data.get("messages", 0)), aircraft)


def _aircraft(entry: dict[str, Any], receiver: LatLonDeg, observed_at: datetime) -> Aircraft | None:
    lat, lon = entry.get("lat"), entry.get("lon")
    if lat is None or lon is None:
        return None
    position = (float(lat), float(lon))

    alt_baro = entry.get("alt_baro")
    on_ground = alt_baro == "ground"
    if on_ground:
        altitude_ft: float | None = 0.0
    else:
        altitude_ft = _number(alt_baro if alt_baro is not None else entry.get("alt_geom"))
    altitude_m = None if altitude_ft is None else units.m_from_ft(altitude_ft)

    speed_kt = _number(entry.get("gs"))
    rate_ft_per_min = _number(entry.get("baro_rate", entry.get("geom_rate")))

    distance_m = geomath.distance_m(receiver, position)
    elevation_deg = (
        None if altitude_m is None else geomath.elevation_angle_deg(distance_m, altitude_m)
    )

    flight = (entry.get("flight") or "").strip() or None
    return Aircraft(
        hex=str(entry["hex"]).lower(),
        flight=flight,
        registration=entry.get("r") or None,
        aircraft_type=entry.get("t") or None,
        lat_deg=position[0],
        lon_deg=position[1],
        altitude_m=altitude_m,
        on_ground=on_ground,
        ground_speed_m_per_s=None if speed_kt is None else units.m_per_s_from_kt(speed_kt),
        track_deg=_number(entry.get("track")),
        vertical_rate_m_per_s=(
            None if rate_ft_per_min is None else units.m_per_s_from_ft_per_min(rate_ft_per_min)
        ),
        squawk=entry.get("squawk") or None,
        rssi_db=_number(entry.get("rssi")),
        seen_s=_number(entry.get("seen")) or 0.0,
        seen_pos_s=_number(entry.get("seen_pos")) or 0.0,
        distance_m=distance_m,
        bearing_deg=geomath.bearing_deg(receiver, position),
        elevation_deg=elevation_deg,
        observed_at=observed_at,
    )


def _number(value: Any) -> float | None:
    """readsb mixes numbers and strings (``"ground"``) in numeric fields."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
