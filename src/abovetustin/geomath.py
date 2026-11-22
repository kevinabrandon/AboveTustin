"""Geometry on the Earth's surface, and the unit conversions the bot reports in.

Positions are ``(latitude, longitude)`` pairs in decimal degrees. Distances are
statute miles and altitudes are feet unless a name says otherwise, which is how
the posts have always read.
"""

import math

EARTH_RADIUS_MI = 3956.0
FEET_PER_MILE = 5280.0
KM_PER_MILE = 1.60934
NM_PER_MILE = 0.868976
MPH_PER_KNOT = 1.15078
METERS_PER_FOOT = 0.3048

type LatLon = tuple[float, float]

_COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def distance(a: LatLon, b: LatLon) -> float:
    """Great-circle distance between two positions, in statute miles (haversine)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def bearing(a: LatLon, b: LatLon) -> float:
    """Initial compass bearing from ``a`` to ``b`` in degrees, 0 <= bearing < 360."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def elevation_angle(distance_mi: float, altitude_ft: float) -> float:
    """Angle above the horizon, in degrees, of a point ``altitude_ft`` up and
    ``distance_mi`` away along the ground.

    Treats the ground as flat, which is fine for the few miles the bot cares
    about. Directly overhead is 90.
    """
    return math.degrees(math.atan2(altitude_ft, distance_mi * FEET_PER_MILE))


def heading_str(heading: float | None) -> str:
    """Eight-point compass label for a heading in degrees, or ``"?"`` if unknown."""
    if heading is None:
        return "?"
    index = int(((heading % 360) + 22.5) // 45) % 8
    return _COMPASS_POINTS[index]


def knots_to_mph(knots: float) -> float:
    return knots * MPH_PER_KNOT


def miles_to_km(miles: float) -> float:
    return miles * KM_PER_MILE


def miles_to_nm(miles: float) -> float:
    return miles * NM_PER_MILE


def feet_to_meters(feet: float) -> float:
    return feet * METERS_PER_FOOT
