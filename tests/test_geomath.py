import math

import pytest

from abovetustin import geomath

LAX = (33.9425, -118.4081)
SFO = (37.6213, -122.3790)


class TestDistance:
    def test_lax_to_sfo(self):
        # Spherical law of cosines with the same radius gives 543 610 m.
        assert geomath.distance_m(LAX, SFO) == pytest.approx(543_610, abs=1)

    def test_is_symmetric(self):
        assert geomath.distance_m(LAX, SFO) == pytest.approx(geomath.distance_m(SFO, LAX))

    def test_same_point_is_zero(self):
        assert geomath.distance_m(LAX, LAX) == 0.0

    def test_one_degree_of_latitude(self):
        # 2 * pi * R / 360 with R = 6 371 008.8 m.
        assert geomath.distance_m((10.0, 20.0), (11.0, 20.0)) == pytest.approx(111_195.1, abs=0.1)


class TestBearing:
    @pytest.mark.parametrize(
        ("target", "expected_deg"),
        [((1.0, 0.0), 0.0), ((0.0, 1.0), 90.0), ((-1.0, 0.0), 180.0), ((0.0, -1.0), 270.0)],
    )
    def test_cardinal_directions_from_origin(self, target, expected_deg):
        assert geomath.bearing_deg((0.0, 0.0), target) == pytest.approx(expected_deg)

    def test_result_is_normalised(self):
        b = geomath.bearing_deg(SFO, LAX)
        assert 0.0 <= b < 360.0
        # LAX is south-east of SFO.
        assert 90.0 < b < 180.0


class TestElevationAngle:
    def test_equal_height_and_distance_is_45_degrees(self):
        assert geomath.elevation_angle_deg(1500.0, 1500.0) == pytest.approx(45.0)

    def test_directly_overhead(self):
        assert geomath.elevation_angle_deg(0.0, 1500.0) == 90.0

    def test_on_the_ground_far_away(self):
        assert geomath.elevation_angle_deg(16_000.0, 0.0) == 0.0

    def test_matches_v1_formula_where_v1_was_defined(self):
        # v1: degrees(atan(alt_ft / (dist_mi * 5280))). Units cancel, so the
        # same ratio in metres must give the same angle.
        v1 = math.degrees(math.atan(4100.0 / (2.3 * 5280)))
        assert geomath.elevation_angle_deg(2.3 * 5280, 4100.0) == pytest.approx(v1)


class TestCompassPoint:
    @pytest.mark.parametrize(
        ("heading_deg", "expected"),
        [
            (0.0, "N"),
            (22.4, "N"),
            (22.5, "NE"),
            (45.0, "NE"),
            (67.5, "E"),
            (90.0, "E"),
            (135.0, "SE"),
            (180.0, "S"),
            (225.0, "SW"),
            (270.0, "W"),
            (315.0, "NW"),
            (337.4, "NW"),
            (337.5, "N"),
            (359.9, "N"),
            (360.0, "N"),
            (-90.0, "W"),
        ],
    )
    def test_compass_points_and_boundaries(self, heading_deg, expected):
        assert geomath.compass_point(heading_deg) == expected

    def test_unknown_heading(self):
        assert geomath.compass_point(None) == "?"
