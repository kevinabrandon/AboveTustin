"""The alarm-zone tracker, carried over from v1.

An aircraft is *in the alarm zone* when it is closer than ``distance_alarm_m``
or higher above the horizon than ``elevation_alarm_deg``. While it is in the
zone the tracker remembers the sample at its closest approach. Once it has
been out of the zone for ``wait_updates`` consecutive polls the tracker
emits a :class:`Sighting` built from that sample and forgets the aircraft.
Coming back into the zone before then resets the count, and a closer pass
replaces the remembered sample.

Pure logic: no clock, no I/O. Feed it the aircraft from each poll and it
returns the sightings that completed on that poll.

Differences from v1 ``tracker.py``, both deliberate:

* v1 only reset the out-of-zone count when the aircraft set a new closest
  approach; v2 resets it whenever the aircraft is seen in the zone.
* v1 posted on the poll after ``wait_x_updates`` misses; v2 emits on the
  ``wait_updates``-th miss. The default is one lower to compensate.
* A position older than ``max_position_age_s`` counts as absent, so an
  aircraft that drops out of coverage inside the zone does not sit there
  until readsb forgets it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from abovetustin.aircraft import Aircraft


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    distance_alarm_m: float
    elevation_alarm_deg: float
    #: Consecutive polls out of the zone before the sighting is emitted.
    wait_updates: int = 4
    #: Samples whose position is older than this are treated as absent.
    max_position_age_s: float = 30.0

    def in_zone(self, aircraft: Aircraft) -> bool:
        if aircraft.seen_pos_s > self.max_position_age_s:
            return False
        if aircraft.distance_m < self.distance_alarm_m:
            return True
        return (
            aircraft.elevation_deg is not None and aircraft.elevation_deg > self.elevation_alarm_deg
        )


@dataclass(frozen=True, slots=True)
class Sighting:
    """One pass through the alarm zone, summarised at closest approach."""

    closest: Aircraft
    first_seen_at: datetime
    last_seen_at: datetime
    #: Polls on which the aircraft was in the zone.
    samples: int


@dataclass(slots=True)
class _Track:
    closest: Aircraft
    first_seen_at: datetime
    last_seen_at: datetime
    samples: int = 1
    misses: int = 0

    def sighting(self) -> Sighting:
        return Sighting(self.closest, self.first_seen_at, self.last_seen_at, self.samples)


class Tracker:
    def __init__(self, config: TrackerConfig) -> None:
        self.config = config
        self._tracks: dict[str, _Track] = {}

    def update(self, aircraft: Iterable[Aircraft]) -> list[Sighting]:
        """Record one poll and return the sightings that completed on it."""
        present = {a.hex: a for a in aircraft if self.config.in_zone(a)}

        for hex_code, sample in present.items():
            track = self._tracks.get(hex_code)
            if track is None:
                self._tracks[hex_code] = _Track(sample, sample.observed_at, sample.observed_at)
                continue
            track.misses = 0
            track.samples += 1
            track.last_seen_at = sample.observed_at
            if sample.distance_m < track.closest.distance_m:
                track.closest = sample

        completed: list[Sighting] = []
        for hex_code in [h for h in self._tracks if h not in present]:
            track = self._tracks[hex_code]
            track.misses += 1
            if track.misses >= self.config.wait_updates:
                completed.append(track.sighting())
                del self._tracks[hex_code]
        return completed

    def in_progress(self) -> list[Sighting]:
        """Aircraft currently being tracked, as provisional sightings."""
        return [t.sighting() for t in self._tracks.values()]
