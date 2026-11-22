import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from abovetustin import geomath
from abovetustin.source import readsb

# The v1 receiver position, which every fixture is translated onto.
RECEIVER = (33.754271, -117.823096)

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "readsb").glob("*.jsonl"))


def sample_document():
    return {
        "now": 1767225600.5,
        "messages": 123456,
        "aircraft": [
            {  # airliner overhead-ish, every field the parser reads
                "hex": "a1b2c3",
                "type": "adsb_icao",
                "flight": "TEST001 ",
                "r": "N12345",
                "t": "B738",
                "alt_baro": 35000,
                "alt_geom": 35600,
                "gs": 450.0,
                "track": 312.4,
                "baro_rate": -1024,
                "squawk": "2200",
                "lat": 33.764271,  # 0.01 deg north of the receiver
                "lon": -117.823096,
                "seen_pos": 0.3,
                "rssi": -12.5,
                "seen": 0.1,
                "messages": 400,
            },
            {  # on the ground
                "hex": "d4e5f6",
                "alt_baro": "ground",
                "gs": 12.0,
                "lat": 33.70,
                "lon": -117.86,
                "seen": 2.0,
            },
            {  # MLAT with a synthetic address and no altitude
                "hex": "~f00001",
                "type": "mlat",
                "lat": 33.80,
                "lon": -117.80,
                "geom_rate": 64,
            },
            {  # no position: cannot be placed, so dropped
                "hex": "abcdef",
                "flight": "NOPOS   ",
                "alt_baro": 1200,
            },
        ],
    }


class TestParse:
    def test_snapshot_header(self):
        snap = readsb.parse(sample_document(), RECEIVER)
        assert snap.observed_at == datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=UTC)
        assert snap.messages == 123456

    def test_aircraft_without_a_position_are_dropped(self):
        snap = readsb.parse(sample_document(), RECEIVER)
        assert [a.hex for a in snap.aircraft] == ["a1b2c3", "d4e5f6", "~f00001"]

    def test_airliner_fields_in_si(self):
        a = readsb.parse(sample_document(), RECEIVER).aircraft[0]
        assert a.flight == "TEST001"
        assert a.registration == "N12345"
        assert a.aircraft_type == "B738"
        assert a.altitude_m == pytest.approx(10_668.0)
        assert a.on_ground is False
        assert a.ground_speed_m_per_s == pytest.approx(231.5, abs=0.01)
        assert a.track_deg == 312.4
        assert a.vertical_rate_m_per_s == pytest.approx(-5.2019, abs=1e-4)
        assert a.squawk == "2200"
        assert a.rssi_db == -12.5
        assert a.seen_s == 0.1
        assert a.seen_pos_s == 0.3
        assert a.observed_at == datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=UTC)

    def test_geometry_relative_to_receiver(self):
        a = readsb.parse(sample_document(), RECEIVER).aircraft[0]
        # 0.01 degrees of latitude is 1 112 m due north.
        assert a.distance_m == pytest.approx(1112.0, abs=0.5)
        assert a.bearing_deg == pytest.approx(0.0, abs=1e-6)
        expected_deg = geomath.elevation_angle_deg(a.distance_m, 10_668.0)
        assert a.elevation_deg == pytest.approx(expected_deg)
        assert 83.0 < a.elevation_deg < 85.0

    def test_on_ground(self):
        a = readsb.parse(sample_document(), RECEIVER).aircraft[1]
        assert a.on_ground is True
        assert a.altitude_m == 0.0
        assert a.elevation_deg == 0.0
        assert a.flight is None
        assert a.ident == "D4E5F6"

    def test_mlat_without_altitude(self):
        a = readsb.parse(sample_document(), RECEIVER).aircraft[2]
        assert a.is_anonymous is True
        assert a.altitude_m is None
        assert a.elevation_deg is None
        assert a.ground_speed_m_per_s is None
        assert a.vertical_rate_m_per_s == pytest.approx(0.32512)
        assert a.seen_s == 0.0

    def test_ident_prefers_callsign_then_registration(self):
        snap = readsb.parse(sample_document(), RECEIVER)
        assert snap.aircraft[0].ident == "TEST001"
        doc = sample_document()
        del doc["aircraft"][0]["flight"]
        assert readsb.parse(doc, RECEIVER).aircraft[0].ident == "N12345"

    def test_empty_sky(self):
        snap = readsb.parse({"now": 1767225600, "messages": 0, "aircraft": []}, RECEIVER)
        assert snap.aircraft == ()


@pytest.mark.skipif(not FIXTURES, reason="no recorded fixtures")
@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_recorded_fixtures_parse(path):
    """Every recorded snapshot parses, time moves forward, and every aircraft
    sits where a translation onto the v1 receiver would put it."""
    previous = None
    total = 0
    for line in path.read_text().splitlines():
        snap = readsb.parse(json.loads(line), RECEIVER)
        assert previous is None or snap.observed_at > previous
        previous = snap.observed_at
        for a in snap.aircraft:
            assert a.distance_m < 700_000  # readsb's max range is 450 nmi
            assert 0.0 <= a.bearing_deg < 360.0
            assert a.elevation_deg is None or -1.0 <= a.elevation_deg <= 90.0
            assert a.registration is None  # scrubbed
            assert a.flight is None or a.flight.startswith("TEST")
        total += len(snap.aircraft)
    assert total > 0
