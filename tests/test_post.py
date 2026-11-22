import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from abovetustin.aircraft import Aircraft
from abovetustin.post import Post, jsonl, text
from abovetustin.post.images import ImageDirectory
from abovetustin.tracker import Sighting

T0 = datetime(2026, 1, 1, 20, 2, 31, tzinfo=UTC)

CLOSEST = Aircraft(
    hex="a1b2c3",
    flight="TEST001",
    registration="N12345",
    aircraft_type="CRJ2",
    lat_deg=33.75,
    lon_deg=-117.82,
    altitude_m=487.68,  # 1,600 ft
    on_ground=False,
    ground_speed_m_per_s=59.0,  # 132 mph
    track_deg=225.0,
    vertical_rate_m_per_s=-3.0,
    squawk="2200",
    rssi_db=-8.1,
    seen_s=0.1,
    seen_pos_s=0.2,
    distance_m=321.87,  # 0.2 mi
    bearing_deg=190.0,
    elevation_deg=59.7,
    observed_at=T0,
)
SIGHTING = Sighting(CLOSEST, T0 - timedelta(seconds=12), T0 + timedelta(seconds=9), samples=22)


class TestSummary:
    def test_full(self):
        assert text.summary(SIGHTING, tz=UTC) == (
            "TEST001: 0.2 mi away at 1,600 ft, 59.7° above the horizon, "
            "heading SW at 132 mph, 20:02:31"
        )

    def test_gaps_are_left_out(self):
        bare = replace(
            CLOSEST,
            flight=None,
            registration=None,
            altitude_m=None,
            elevation_deg=None,
            track_deg=None,
            ground_speed_m_per_s=None,
        )
        assert text.summary(replace(SIGHTING, closest=bare), tz=UTC) == (
            "A1B2C3: 0.2 mi away, 20:02:31"
        )

    def test_on_the_ground(self):
        grounded = replace(CLOSEST, on_ground=True, altitude_m=0.0, elevation_deg=0.0)
        assert text.summary(replace(SIGHTING, closest=grounded), tz=UTC).startswith(
            "TEST001: 0.2 mi away, on the ground, 0.0° above the horizon"
        )

    def test_speed_without_heading_is_omitted(self):
        no_track = replace(CLOSEST, track_deg=None)
        assert "mph" not in text.summary(replace(SIGHTING, closest=no_track), tz=UTC)


class TestJsonl:
    def test_record_is_json_ready_and_si(self):
        rec = jsonl.record(SIGHTING)
        json.dumps(rec)
        assert rec["schema"] == 1
        assert rec["samples"] == 22
        assert rec["first_seen_at"] == "2026-01-01T20:02:19+00:00"
        assert rec["closest"]["hex"] == "a1b2c3"
        assert rec["closest"]["distance_m"] == 321.87
        assert rec["closest"]["observed_at"] == "2026-01-01T20:02:31+00:00"

    def test_appends_one_line_per_sighting(self, tmp_path):
        path = tmp_path / "deep" / "sightings.jsonl"
        log = jsonl.JsonlLog(path)
        log.post(Post(SIGHTING, b"png"))
        log.post(Post(replace(SIGHTING, samples=1)))
        lines = path.read_text().splitlines()
        assert len(lines) == 2
        assert [json.loads(line)["samples"] for line in lines] == [22, 1]
        assert [json.loads(line)["image"] for line in lines] == [
            "20260101T200231Z_a1b2c3.png",
            None,
        ]
        assert "\n" not in lines[0]


class TestImages:
    def test_name_strips_the_anonymous_marker(self):
        anon = replace(CLOSEST, hex="~f00001")
        assert Post(replace(SIGHTING, closest=anon)).image_name == "20260101T200231Z_f00001.png"

    def test_directory_writes_images_and_skips_posts_without(self, tmp_path):
        sink = ImageDirectory(tmp_path / "images")
        sink.post(Post(SIGHTING, b"\x89PNG"))
        sink.post(Post(replace(SIGHTING, samples=1)))
        files = sorted(p.name for p in (tmp_path / "images").iterdir())
        assert files == ["20260101T200231Z_a1b2c3.png"]
        assert (tmp_path / "images" / files[0]).read_bytes() == b"\x89PNG"

    def test_record_round_trips_through_json(self):
        assert json.loads(json.dumps(jsonl.record(SIGHTING))) == jsonl.record(SIGHTING)


def test_summary_defaults_to_local_time():
    # Just that it runs and ends in a clock time; the zone depends on the machine.
    assert text.summary(SIGHTING)[-8:].count(":") == 2


@pytest.mark.parametrize("field", ["distance_m", "altitude_m", "ground_speed_m_per_s"])
def test_record_keeps_si_field_names(field):
    assert field in jsonl.record(SIGHTING)["closest"]
