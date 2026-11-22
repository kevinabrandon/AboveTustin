"""One aircraft as seen from the receiver at one instant."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Aircraft:
    """A single aircraft sample, in SI units, relative to the receiver.

    Everything a data source cannot supply is ``None``; the tracker and the
    post templates decide what to do about gaps.
    """

    #: 24-bit address as six lower-case hex digits. A leading ``~`` marks a
    #: synthetic address assigned by MLAT or TIS-B, which identifies nothing.
    hex: str
    flight: str | None
    registration: str | None
    aircraft_type: str | None
    lat_deg: float
    lon_deg: float
    altitude_m: float | None
    on_ground: bool
    ground_speed_m_per_s: float | None
    track_deg: float | None
    vertical_rate_m_per_s: float | None
    squawk: str | None
    rssi_db: float | None
    #: Seconds since the last message, and since the last position.
    seen_s: float
    seen_pos_s: float
    #: Relative to the receiver.
    distance_m: float
    bearing_deg: float
    elevation_deg: float | None
    observed_at: datetime

    @property
    def is_anonymous(self) -> bool:
        return self.hex.startswith("~")

    @property
    def ident(self) -> str:
        """Best human label: callsign, else registration, else the address."""
        return self.flight or self.registration or self.hex.upper()
