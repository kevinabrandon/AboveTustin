"""Geometry on the Earth's surface.

Positions are ``(latitude_deg, longitude_deg)`` pairs. Lengths are metres,
angles are degrees; see ``abovetustin.units`` for the policy and the one
sanctioned exception (angles stay in degrees rather than radians).
"""

import math

#: IUGG mean Earth radius R1 = (2a + b) / 3 for the WGS 84 ellipsoid.
#: v1 used 3956 statute miles (6 366.6 km), about 0.07 % smaller; posted
#: distances change in the second decimal place at most.
EARTH_MEAN_RADIUS_M = 6_371_008.8

type LatLonDeg = tuple[float, float]

_COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def distance_m(a: LatLonDeg, b: LatLonDeg) -> float:
    """Great-circle distance between two positions, in metres (haversine)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_MEAN_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a: LatLonDeg, b: LatLonDeg) -> float:
    """Initial compass bearing from ``a`` to ``b`` in degrees, 0 <= bearing < 360."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def elevation_angle_deg(ground_distance_m: float, altitude_m: float) -> float:
    """Angle above the horizon of a point ``altitude_m`` up and
    ``ground_distance_m`` away along the ground.

    Treats the ground as flat, which is fine for the few kilometres the bot
    cares about. Directly overhead is 90.
    """
    return math.degrees(math.atan2(altitude_m, ground_distance_m))


def compass_point(heading_deg: float | None) -> str:
    """Eight-point compass label for a heading, or ``"?"`` if unknown."""
    if heading_deg is None:
        return "?"
    index = int(((heading_deg % 360) + 22.5) // 45) % 8
    return _COMPASS_POINTS[index]
