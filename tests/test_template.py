from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from abovetustin.aircraft import Aircraft
from abovetustin.post import template
from abovetustin.post.template import PostConfig, Rule
from abovetustin.tracker import Sighting

PACIFIC = ZoneInfo("America/Los_Angeles")
# 2026-01-02 is a Friday; 04:02:31 UTC is 20:02:31 the previous evening in LA.
T0 = datetime(2026, 1, 2, 4, 2, 31, tzinfo=UTC)

CLOSEST = Aircraft(
    hex="a1b2c3",
    flight="SKW4530",
    registration="N456SW",
    aircraft_type="CRJ2",
    lat_deg=33.75,
    lon_deg=-117.82,
    altitude_m=487.68,  # 1,600 ft
    on_ground=False,
    ground_speed_m_per_s=59.14,  # 132 mph
    track_deg=225.0,
    vertical_rate_m_per_s=-5.08,  # -1,000 ft/min
    squawk="2200",
    rssi_db=-8.1,
    seen_s=0.1,
    seen_pos_s=0.2,
    distance_m=321.87,  # 0.2 mi
    bearing_deg=190.4,
    elevation_deg=59.7,
    observed_at=T0,
)
SIGHTING = Sighting(CLOSEST, T0 - timedelta(seconds=12), T0 + timedelta(seconds=9), samples=22)

V1_TEMPLATE = (
    "#${flight} : ${dist_mi} mi away @ ${alt_ft} ft and ${el}° frm hrzn, "
    "heading ${heading} @ ${speed_mph}mi/h ${time}."
)


class TestVariables:
    def test_v1_post_reproduced(self):
        text = template.compose(SIGHTING, PostConfig(V1_TEMPLATE, tz=PACIFIC), 300)
        assert text == (
            "#SKW4530 : 0.2 mi away @ 1600 ft and 59.7° frm hrzn, heading SW @ 132mi/h 20:02:31."
        )

    def test_every_variable_renders(self):
        v = template.variables(SIGHTING, PACIFIC)
        assert set(v) == set(template.VARIABLES)
        assert v["icao"] == "A1B2C3"
        assert v["registration"] == "N456SW"
        assert v["type"] == "CRJ2"
        assert v["dist_km"] == "0.3" and v["dist_nm"] == "0.2"
        assert v["alt_m"] == "488"
        assert v["az"] == "190" and v["track"] == "225"
        assert v["speed_kmph"] == "213" and v["speed_kts"] == "115"
        assert v["vert_rate_ftpm"] == "-1000" and v["vert_rate_mpm"] == "-305"
        assert v["squawk"] == "2200" and v["rssi"] == "-8.1"
        assert v["date"] == "2026-01-01"

    def test_unknowns_render_as_question_marks(self):
        bare = replace(
            CLOSEST,
            flight=None,
            registration=None,
            aircraft_type=None,
            altitude_m=None,
            elevation_deg=None,
            track_deg=None,
            ground_speed_m_per_s=None,
            vertical_rate_m_per_s=None,
            squawk=None,
            rssi_db=None,
        )
        v = template.variables(replace(SIGHTING, closest=bare), UTC)
        assert v["flight"] == "A1B2C3"
        for key in ("registration", "type", "alt_ft", "el", "heading", "speed_mph", "squawk"):
            assert v[key] == "?", key

    def test_time_follows_the_configured_zone(self):
        assert template.variables(SIGHTING, UTC)["time"] == "04:02:31"
        assert template.variables(SIGHTING, PACIFIC)["time"] == "20:02:31"


class TestValidateTemplate:
    def test_accepts_known_variables(self):
        template.validate_template(V1_TEMPLATE)

    def test_rejects_unknown_variable(self):
        with pytest.raises(template.TemplateError, match="unknown template variable.*altitude"):
            template.validate_template("${flight} at ${altitude}")

    def test_rejects_malformed(self):
        with pytest.raises(template.TemplateError, match="malformed"):
            template.validate_template("cost: $5")


class TestRules:
    LOCAL = T0.astimezone(PACIFIC)

    def match(self, **kw):
        return Rule(**kw).matches(SIGHTING, self.LOCAL)

    def test_no_conditions_always_matches(self):
        assert self.match(tag="#x")

    def test_altitude_band(self):
        assert self.match(altitude_min_m=304.8, altitude_max_m=762.0)  # 1,000 to 2,500 ft
        assert not self.match(altitude_max_m=304.8)
        assert not self.match(altitude_min_m=762.0)

    def test_heading_band_and_wrap(self):
        assert self.match(heading_min_deg=157.5, heading_max_deg=247.5)  # S through SW
        assert not self.match(heading_min_deg=315.0, heading_max_deg=45.0)
        north = replace(SIGHTING, closest=replace(CLOSEST, track_deg=10.0))
        assert Rule(heading_min_deg=315.0, heading_max_deg=45.0).matches(north, self.LOCAL)

    def test_hours_window_crossing_midnight(self):
        assert not self.match(hours=(time(23, 0), time(7, 0)))  # 20:02 is not after hours
        late = replace(SIGHTING, closest=replace(CLOSEST, observed_at=T0 + timedelta(hours=4)))
        assert Rule(hours=(time(23, 0), time(7, 0))).matches(
            late, (T0 + timedelta(hours=4)).astimezone(PACIFIC)
        )
        assert self.match(hours=(time(19, 0), time(21, 0)))

    def test_weekdays(self):
        assert self.match(weekdays=frozenset({"thu"}))  # Thursday evening in LA
        assert not self.match(weekdays=frozenset({"fri"}))

    def test_speed_distance_elevation_vertical_rate(self):
        assert self.match(speed_min_m_per_s=50.0, speed_max_m_per_s=70.0)
        assert self.match(distance_max_m=500.0)
        assert self.match(elevation_min_deg=50.0)
        assert self.match(vertical_rate_max_m_per_s=-2.0)  # descending
        assert not self.match(vertical_rate_min_m_per_s=0.0)

    def test_anonymous_and_ground_flags(self):
        assert self.match(anonymous=False)
        assert not self.match(anonymous=True)
        anon = replace(SIGHTING, closest=replace(CLOSEST, hex="~f00001", flight=None))
        assert Rule(anonymous=True).matches(anon, self.LOCAL)
        assert self.match(on_ground=False)

    def test_unknown_value_fails_a_range_condition(self):
        no_alt = replace(SIGHTING, closest=replace(CLOSEST, altitude_m=None))
        assert not Rule(altitude_min_m=0.0).matches(no_alt, self.LOCAL)
        assert Rule(tag="#x").matches(no_alt, self.LOCAL)

    def test_all_conditions_must_hold(self):
        assert not self.match(altitude_max_m=762.0, heading_min_deg=0.0, heading_max_deg=90.0)


class TestCompose:
    CONFIG = PostConfig(
        template="${flight}: ${dist_mi} mi, ${alt_ft} ft",
        hashtags=("#ADSB", "#readsb"),
        rules=(
            Rule(
                tag="#ProbablyLanding",
                altitude_min_m=304.8,
                altitude_max_m=762.0,
                heading_min_deg=157.5,
                heading_max_deg=247.5,
            ),
            Rule(tag="#AfterHours", hours=(time(23, 0), time(7, 0))),
            Rule(tag="#2CloseForComfort", altitude_max_m=304.8),
            Rule(template="Anonymous aircraft: ${dist_mi} mi, ${alt_ft} ft", anonymous=True),
        ),
        tz=PACIFIC,
    )

    def test_rule_tags_then_standing_hashtags(self):
        assert template.compose(SIGHTING, self.CONFIG, 300) == (
            "SKW4530: 0.2 mi, 1600 ft #ProbablyLanding #ADSB #readsb"
        )

    def test_tags_dropped_when_they_do_not_fit(self):
        assert template.compose(SIGHTING, self.CONFIG, 45) == (
            "SKW4530: 0.2 mi, 1600 ft #ProbablyLanding"
        )
        assert template.compose(SIGHTING, self.CONFIG, 50) == (
            "SKW4530: 0.2 mi, 1600 ft #ProbablyLanding #ADSB"
        )

    def test_rule_template_replaces_the_base(self):
        anon = replace(
            SIGHTING, closest=replace(CLOSEST, hex="~f00001", flight=None, registration=None)
        )
        assert template.compose(anon, self.CONFIG, 300) == (
            "Anonymous aircraft: 0.2 mi, 1600 ft #ProbablyLanding #ADSB #readsb"
        )

    def test_first_matching_template_wins(self):
        config = replace(
            self.CONFIG,
            rules=(Rule(template="first ${flight}"), Rule(template="second ${flight}")),
        )
        assert template.compose(SIGHTING, config, 300) == "first SKW4530 #ADSB #readsb"

    def test_tag_already_in_text_is_not_repeated(self):
        config = replace(self.CONFIG, template="#ADSB ${flight}")
        assert template.compose(SIGHTING, config, 300) == "#ADSB SKW4530 #ProbablyLanding #readsb"

    def test_no_rules_no_hashtags(self):
        assert template.compose(SIGHTING, PostConfig("${flight}"), 300) == "SKW4530"
