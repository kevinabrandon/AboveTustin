import pint
import pytest

from abovetustin import units


class TestParse:
    def test_statute_miles_to_metres(self):
        assert units.parse("1.2 mi", "m") == pytest.approx(1931.2128)

    def test_kilometres_to_metres(self):
        assert units.parse("2 km", "m") == 2000.0

    def test_knots_to_metres_per_second(self):
        assert units.parse("100 knot", "m/s") == pytest.approx(51.4444, abs=1e-4)

    def test_wrong_dimension_is_rejected(self):
        with pytest.raises(pint.DimensionalityError):
            units.parse("1.2 mi", "m/s")

    def test_bare_number_is_rejected(self):
        with pytest.raises(pint.DimensionalityError):
            units.parse("1.2", "m")


def test_si_of_quantity():
    assert units.si(units.Quantity(5000, "ft")) == pytest.approx(1524.0)


def test_display_conversion_through_quantity():
    assert units.Quantity(1609.344, "m").to("mi").magnitude == pytest.approx(1.0)


class TestParserHelpers:
    def test_feet_to_metres(self):
        assert units.m_from_ft(35_000.0) == pytest.approx(10_668.0)

    def test_knots_to_metres_per_second(self):
        assert units.m_per_s_from_kt(450.0) == pytest.approx(231.5, abs=0.01)

    def test_feet_per_minute_to_metres_per_second(self):
        assert units.m_per_s_from_ft_per_min(-1024.0) == pytest.approx(-5.2019, abs=1e-4)
