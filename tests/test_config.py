from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from abovetustin import config

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"

MINIMAL = """
[receiver]
latitude_deg = 33.7458
longitude_deg = -117.8261

[tracker]
distance_alarm = "2 km"
elevation_alarm_deg = 45
"""


def test_example_file_parses():
    cfg = config.load(EXAMPLE)
    assert cfg.receiver == (33.7458, -117.8261)
    assert cfg.source.url == "http://localhost/tar1090/data/aircraft.json"
    assert cfg.source.poll_interval_s == 1.0
    assert cfg.source.timeout_s == 10.0
    assert cfg.tracker.distance_alarm_m == pytest.approx(1931.2128)
    assert cfg.tracker.elevation_alarm_deg == 50.0
    assert cfg.tracker.wait_updates == 4
    assert cfg.tracker.max_position_age_s == 30.0
    assert cfg.log_path == Path("~/.local/share/abovetustin/sightings.jsonl").expanduser()
    assert cfg.render is not None
    assert cfg.render.url == "http://localhost/tar1090/"
    assert cfg.render.zoom == 11
    assert cfg.render.grid_deg == 0.1
    assert cfg.render.center == "grid"
    assert cfg.render.show_receiver is False
    assert cfg.render.ring_distances_m == pytest.approx((1609.344, 3218.688, 8046.72))
    assert cfg.render.reload_after_s == 3600.0
    assert cfg.image_dir == Path("~/.local/share/abovetustin/images").expanduser()
    assert cfg.post.template == config.DEFAULT_TEMPLATE
    assert cfg.post.hashtags == ("#ADSB", "#readsb")
    assert cfg.post.tz is None
    assert [r.tag for r in cfg.post.rules] == [
        "#AfterHours",
        "#2CloseForComfort",
        "#ProbablyLanding",
        "#UpInTheClouds",
        "#WayTheHeckUpThere",
        "#MovingQuickly",
        "#FlyingFast",
        None,
    ]
    landing = cfg.post.rules[2]
    assert landing.altitude_min_m == pytest.approx(304.8)
    assert landing.altitude_max_m == pytest.approx(762.0)
    assert (landing.heading_min_deg, landing.heading_max_deg) == (157.5, 247.5)
    assert cfg.post.rules[0].hours == (time(23, 0), time(7, 0))
    assert cfg.post.rules[-1].anonymous is True and cfg.post.rules[-1].template
    assert cfg.bluesky is None


class TestPostSection:
    def test_timezone_and_weekdays(self):
        cfg = config.parse(
            MINIMAL
            + '[post]\ntimezone = "America/Los_Angeles"\n'
            + '[[post.rules]]\ntag = "#Weekend"\nweekdays = ["Saturday", "sun"]\n'
        )
        assert cfg.post.tz == ZoneInfo("America/Los_Angeles")
        assert cfg.post.rules[0].weekdays == frozenset({"sat", "sun"})

    def test_bad_timezone(self):
        with pytest.raises(config.ConfigError, match="unknown time zone 'Mars/Olympus'"):
            config.parse(MINIMAL + '[post]\ntimezone = "Mars/Olympus"\n')

    def test_bad_template_variable(self):
        with pytest.raises(
            config.ConfigError, match=r"\[post\] template: unknown template variable"
        ):
            config.parse(MINIMAL + '[post]\ntemplate = "${altitude}"\n')

    def test_rule_needs_tag_or_template(self):
        with pytest.raises(
            config.ConfigError, match=r"\[post.rules\[0\]\] needs a tag or a template"
        ):
            config.parse(MINIMAL + '[[post.rules]]\naltitude_max = "1000 ft"\n')

    def test_rule_unknown_key(self):
        with pytest.raises(
            config.ConfigError, match=r"post.rules\[0\]\] unknown key\(s\): altitude"
        ):
            config.parse(MINIMAL + '[[post.rules]]\ntag = "#x"\naltitude = "1000 ft"\n')

    def test_rule_bad_hours_and_weekday(self):
        with pytest.raises(config.ConfigError, match='hours must look like "23:00-07:00"'):
            config.parse(MINIMAL + '[[post.rules]]\ntag = "#x"\nhours = "late"\n')
        with pytest.raises(config.ConfigError, match="unknown day"):
            config.parse(MINIMAL + '[[post.rules]]\ntag = "#x"\nweekdays = ["funday"]\n')

    def test_rule_quantity_dimension(self):
        with pytest.raises(config.ConfigError, match="speed_min: '300 ft'"):
            config.parse(MINIMAL + '[[post.rules]]\ntag = "#x"\nspeed_min = "300 ft"\n')

    def test_rules_must_be_an_array_of_tables(self):
        with pytest.raises(config.ConfigError, match="array of tables"):
            config.parse(MINIMAL + '[post]\nrules = "none"\n')


class TestBlueskySection:
    def test_present(self):
        cfg = config.parse(MINIMAL + '[bluesky]\nhandle = "a.b.c"\napp_password = "p"\n')
        assert cfg.bluesky is not None
        assert (cfg.bluesky.handle, cfg.bluesky.app_password) == ("a.b.c", "p")
        assert cfg.bluesky.service == "https://bsky.social"

    def test_missing_password_names_the_key(self):
        with pytest.raises(config.ConfigError, match=r"\[bluesky\] is missing app_password"):
            config.parse(MINIMAL + '[bluesky]\nhandle = "a.b.c"\n')


def test_render_can_be_disabled():
    cfg = config.parse(MINIMAL + "[render]\nenabled = false\n")
    assert cfg.render is None
    with pytest.raises(config.ConfigError, match="enabled must be true or false"):
        config.parse(MINIMAL + '[render]\nenabled = "no"\n')


def test_render_centred_on_the_receiver_with_rings():
    cfg = config.parse(
        MINIMAL + '[render]\ncenter = "receiver"\nshow_receiver = true\nring_distances = ["2 km"]\n'
    )
    assert cfg.render is not None
    assert cfg.render.center == "receiver"
    assert cfg.render.show_receiver is True
    assert cfg.render.ring_distances_m == (2000.0,)


def test_render_bad_centre_and_rings():
    with pytest.raises(
        config.ConfigError, match="center must be one of grid, receiver, aircraft, track"
    ):
        config.parse(MINIMAL + '[render]\ncenter = "house"\n')
    with pytest.raises(config.ConfigError, match="ring_distances must be a list"):
        config.parse(MINIMAL + '[render]\nring_distances = "1 mi"\n')
    with pytest.raises(config.ConfigError, match="not a quantity compatible with 'm'"):
        config.parse(MINIMAL + '[render]\nring_distances = ["1 mi", "30 s"]\n')


def test_minimal_file_fills_defaults():
    cfg = config.parse(MINIMAL)
    assert cfg.tracker.distance_alarm_m == 2000.0
    assert cfg.tracker.elevation_alarm_deg == 45.0
    assert cfg.tracker.wait_updates == 4
    assert cfg.source.poll_interval_s == 1.0
    assert cfg.log_path == config.DEFAULT_LOG_PATH.expanduser()
    assert cfg.render is not None and cfg.render.browser_channel == "chrome"


def test_missing_file(tmp_path):
    with pytest.raises(config.ConfigError, match="no config file"):
        config.load(tmp_path / "nope.toml")


def test_invalid_toml():
    with pytest.raises(config.ConfigError, match="not valid TOML"):
        config.parse("[receiver\n")


def test_missing_section():
    with pytest.raises(config.ConfigError, match=r"missing \[tracker\] section"):
        config.parse("[receiver]\nlatitude_deg = 1\nlongitude_deg = 2\n")


def test_missing_key():
    with pytest.raises(config.ConfigError, match=r"\[receiver\] is missing longitude_deg"):
        config.parse("[receiver]\nlatitude_deg = 1\n[tracker]\n")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("1.2", "must be a string with units"),
        ('"1.2"', "not a quantity compatible with 'm'"),
        ('"30 s"', "not a quantity compatible with 'm'"),
        ('"nonsense"', "not a quantity compatible with 'm'"),
        ('"3 furlongs 2 s"', "not a quantity compatible with 'm'"),
    ],
)
def test_bad_quantities(value, message):
    text = MINIMAL.replace('distance_alarm = "2 km"', f"distance_alarm = {value}")
    with pytest.raises(config.ConfigError, match=message):
        config.parse(text)


def test_wrong_types():
    with pytest.raises(config.ConfigError, match="elevation_alarm_deg must be a number"):
        config.parse(MINIMAL.replace("elevation_alarm_deg = 45", 'elevation_alarm_deg = "45"'))
    with pytest.raises(config.ConfigError, match="wait_updates must be a whole number"):
        config.parse(MINIMAL + "wait_updates = 2.5\n")
