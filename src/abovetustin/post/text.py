"""Human-readable one-liners for sightings.

Boundary module: this is where metres become the miles and feet people
expect to read. The full post templates arrive with the first social
poster; this is the fixed summary used by the log and the dry run.
"""

from __future__ import annotations

from datetime import tzinfo

from abovetustin import geomath, units
from abovetustin.tracker import Sighting


def summary(sighting: Sighting, tz: tzinfo | None = None) -> str:
    """One line, for example::

        TEST001: 0.2 mi away at 1,600 ft, 59.7° above the horizon, heading SW at 132 mph, 20:02:31

    ``tz`` selects the clock the time is shown in; ``None`` means local time.
    """
    a = sighting.closest
    q = units.Quantity
    where = f"{a.ident}: {q(a.distance_m, 'm').to('mi').magnitude:.1f} mi away"
    if a.on_ground:
        where += ", on the ground"
    elif a.altitude_m is not None:
        where += f" at {q(a.altitude_m, 'm').to('ft').magnitude:,.0f} ft"
    parts = [where]
    if a.elevation_deg is not None:
        parts.append(f"{a.elevation_deg:.1f}° above the horizon")
    if a.track_deg is not None:
        heading = f"heading {geomath.compass_point(a.track_deg)}"
        if a.ground_speed_m_per_s is not None:
            heading += f" at {q(a.ground_speed_m_per_s, 'm/s').to('mph').magnitude:.0f} mph"
        parts.append(heading)
    parts.append(a.observed_at.astimezone(tz).strftime("%H:%M:%S"))
    return ", ".join(parts)
