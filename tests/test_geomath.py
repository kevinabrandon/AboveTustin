import math

import pytest

from abovetustin import geomath

LAX = (33.9425, -118.4081)
SFO = (37.6213, -122.3790)


class TestDistance:
    def test_lax_to_sfo(self):
        # Spherical law of cosines with the same radius gives 337.55 mi.
        assert geomath.distance(LAX, SFO) == pytest.approx(337.55, abs=0.05)

    def test_is_symmetric(self):
        assert geomath.distance(LAX, SFO) == pytest.approx(geomath.distance(SFO, LAX))

    def test_same_point_is_zero(self):
        assert geomath.distance(LAX, LAX) == 0.0

    def test_one_degree_of_latitude(self):
        # 2 * pi * R / 360 with R = 3956 mi.
        assert geomath.distance((10.0, 20.0), (11.0, 20.0)) == pytest.approx(69.045, abs=0.001)


class TestBearing:
    @pytest.mark.parametrize(
        ("target", "expected"),
        [((1.0, 0.0), 0.0), ((0.0, 1.0), 90.0), ((-1.0, 0.0), 180.0), ((0.0, -1.0), 270.0)],
    )
    def test_cardinal_directions_from_origin(self, target, expected):
        assert geomath.bearing((0.0, 0.0), target) == pytest.approx(expected)

    def test_result_is_normalised(self):
        b = geomath.bearing(SFO, LAX)
        assert 0.0 <= b < 360.0
        # LAX is south-east of SFO.
        assert 90.0 < b < 180.0


class TestElevationAngle:
    def test_one_mile_up_one_mile_out_is_45_degrees(self):
        assert geomath.elevation_angle(1.0, geomath.FEET_PER_MILE) == pytest.approx(45.0)

    def test_directly_overhead(self):
        assert geomath.elevation_angle(0.0, 5000.0) == 90.0

    def test_on_the_ground_far_away(self):
        assert geomath.elevation_angle(10.0, 0.0) == 0.0

    def test_matches_v1_formula_where_v1_was_defined(self):
        dist_mi, alt_ft = 2.3, 4100.0
        v1 = math.degrees(math.atan(alt_ft / (dist_mi * 5280)))
        assert geomath.elevation_angle(dist_mi, alt_ft) == pytest.approx(v1)


class TestHeadingStr:
    @pytest.mark.parametrize(
        ("heading", "expected"),
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
    def test_compass_points_and_boundaries(self, heading, expected):
        assert geomath.heading_str(heading) == expected

    def test_unknown_heading(self):
        assert geomath.heading_str(None) == "?"


class TestConversions:
    def test_knots_to_mph(self):
        assert geomath.knots_to_mph(100.0) == pytest.approx(115.078)

    def test_miles_to_km(self):
        assert geomath.miles_to_km(100.0) == pytest.approx(160.934)

    def test_miles_to_nm(self):
        assert geomath.miles_to_nm(100.0) == pytest.approx(86.8976)

    def test_feet_to_meters(self):
        assert geomath.feet_to_meters(1000.0) == pytest.approx(304.8)
