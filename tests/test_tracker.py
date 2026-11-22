import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from abovetustin.aircraft import Aircraft
from abovetustin.source import readsb
from abovetustin.tracker import Sighting, Tracker, TrackerConfig

RECEIVER = (33.7458, -117.8261)
# Empty files are a recorder still at work, not fixtures.
FIXTURES = sorted(
    p for p in (Path(__file__).parent / "fixtures" / "readsb").glob("*.jsonl") if p.stat().st_size
)
T0 = datetime(2026, 1, 1, tzinfo=UTC)

# 1 mile and 50 degrees, the v1 defaults, with a short wait so tests stay small.
CONFIG = TrackerConfig(distance_alarm_m=1609.344, elevation_alarm_deg=50.0, wait_updates=3)


def sample(
    hex_code: str = "a1b2c3",
    distance_m: float = 5000.0,
    elevation_deg: float | None = 10.0,
    seen_pos_s: float = 0.0,
    poll: int = 0,
) -> Aircraft:
    """An Aircraft with only the fields the tracker reads set meaningfully."""
    return Aircraft(
        hex=hex_code,
        flight=None,
        registration=None,
        aircraft_type=None,
        lat_deg=0.0,
        lon_deg=0.0,
        altitude_m=1000.0,
        on_ground=False,
        ground_speed_m_per_s=None,
        track_deg=None,
        vertical_rate_m_per_s=None,
        squawk=None,
        rssi_db=None,
        seen_s=0.0,
        seen_pos_s=seen_pos_s,
        distance_m=distance_m,
        bearing_deg=0.0,
        elevation_deg=elevation_deg,
        observed_at=T0 + timedelta(seconds=poll),
    )


def run(tracker: Tracker, polls: list[list[Aircraft]]) -> list[list[Sighting]]:
    return [tracker.update(p) for p in polls]


class TestInZone:
    def test_distance_is_strictly_less_than(self):
        assert CONFIG.in_zone(sample(distance_m=1609.0))
        assert not CONFIG.in_zone(sample(distance_m=1609.344))

    def test_elevation_is_strictly_greater_than(self):
        assert CONFIG.in_zone(sample(distance_m=9000.0, elevation_deg=50.1))
        assert not CONFIG.in_zone(sample(distance_m=9000.0, elevation_deg=50.0))

    def test_unknown_elevation_only_distance_counts(self):
        assert not CONFIG.in_zone(sample(distance_m=9000.0, elevation_deg=None))
        assert CONFIG.in_zone(sample(distance_m=900.0, elevation_deg=None))

    def test_stale_position_is_absent(self):
        assert not CONFIG.in_zone(sample(distance_m=100.0, seen_pos_s=31.0))
        assert CONFIG.in_zone(sample(distance_m=100.0, seen_pos_s=30.0))


class TestPass:
    def test_approach_closest_leave(self):
        polls = [
            [sample(distance_m=5000.0, poll=0)],  # outside
            [sample(distance_m=1200.0, poll=1)],  # enters
            [sample(distance_m=400.0, poll=2)],  # closest
            [sample(distance_m=900.0, poll=3)],  # still in
            [sample(distance_m=2000.0, poll=4)],  # miss 1
            [],  # miss 2
            [sample(distance_m=9000.0, poll=6)],  # miss 3: emit
            [],
        ]
        results = run(Tracker(CONFIG), polls)
        assert [len(r) for r in results] == [0, 0, 0, 0, 0, 0, 1, 0]
        s = results[6][0]
        assert s.closest.distance_m == 400.0
        assert s.first_seen_at == T0 + timedelta(seconds=1)
        assert s.last_seen_at == T0 + timedelta(seconds=3)
        assert s.samples == 3

    def test_elevation_alone_triggers(self):
        polls = [[sample(distance_m=8000.0, elevation_deg=70.0)], [], [], []]
        results = run(Tracker(CONFIG), polls)
        assert [len(r) for r in results] == [0, 0, 0, 1]

    def test_reentry_resets_the_wait(self):
        polls = [
            [sample(distance_m=1000.0, poll=0)],
            [],  # miss 1
            [],  # miss 2
            [sample(distance_m=1500.0, poll=3)],  # back, not closer
            [],  # miss 1 again
            [],  # miss 2
            [],  # miss 3: emit
        ]
        results = run(Tracker(CONFIG), polls)
        assert [len(r) for r in results] == [0, 0, 0, 0, 0, 0, 1]
        s = results[6][0]
        assert s.closest.distance_m == 1000.0
        assert s.samples == 2
        assert s.last_seen_at == T0 + timedelta(seconds=3)

    def test_closer_pass_after_misses_replaces_closest(self):
        polls = [
            [sample(distance_m=1000.0, poll=0)],
            [],
            [sample(distance_m=300.0, poll=2)],
            [],
            [],
            [],
        ]
        results = run(Tracker(CONFIG), polls)
        assert results[5][0].closest.distance_m == 300.0

    def test_out_of_zone_but_visible_counts_as_a_miss(self):
        polls = [
            [sample(distance_m=1000.0)],
            [sample(distance_m=3000.0)],
            [sample(distance_m=4000.0)],
            [sample(distance_m=5000.0)],
        ]
        assert [len(r) for r in run(Tracker(CONFIG), polls)] == [0, 0, 0, 1]

    def test_two_aircraft_are_independent(self):
        a, b = "aaaaaa", "bbbbbb"
        polls = [
            [sample(a, 1000.0), sample(b, 1000.0)],
            [sample(a, 500.0)],
            [sample(a, 800.0)],
            [sample(a, 900.0)],  # b emits here (3 misses)
            [],
            [],
            [],  # a emits here
        ]
        results = run(Tracker(CONFIG), polls)
        assert [[s.closest.hex for s in r] for r in results] == [[], [], [], [b], [], [], [a]]
        assert results[6][0].closest.distance_m == 500.0

    def test_a_second_pass_is_a_second_sighting(self):
        tracker = Tracker(CONFIG)
        one_pass = [[sample(distance_m=1000.0)], [], [], []]
        assert len(run(tracker, one_pass)[-1]) == 1
        assert len(run(tracker, one_pass)[-1]) == 1

    def test_in_progress(self):
        tracker = Tracker(CONFIG)
        assert tracker.in_progress() == []
        tracker.update([sample(distance_m=1000.0)])
        tracker.update([sample(distance_m=700.0, poll=1)])
        [provisional] = tracker.in_progress()
        assert provisional.closest.distance_m == 700.0
        assert provisional.samples == 2
        for _ in range(3):
            tracker.update([])
        assert tracker.in_progress() == []


@pytest.mark.skipif(not FIXTURES, reason="no recorded fixtures")
@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_replay_recorded_fixture(path):
    """Replaying a recording is deterministic and every sighting's closest
    sample was genuinely in the zone."""
    config = TrackerConfig(distance_alarm_m=1931.2128, elevation_alarm_deg=50.0, wait_updates=4)
    snapshots = [readsb.parse(json.loads(line), RECEIVER) for line in path.read_text().splitlines()]

    def replay() -> list[Sighting]:
        tracker = Tracker(config)
        out: list[Sighting] = []
        for snap in snapshots:
            out.extend(tracker.update(snap.aircraft))
        return out

    first, second = replay(), replay()
    assert first == second
    for s in first:
        assert config.in_zone(s.closest)
        assert s.first_seen_at <= s.last_seen_at
