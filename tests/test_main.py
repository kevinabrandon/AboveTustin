import logging
from datetime import UTC, datetime, timedelta

import pytest

from abovetustin import main
from abovetustin.aircraft import Aircraft
from abovetustin.post import Post
from abovetustin.source.readsb import Snapshot
from abovetustin.tracker import Tracker, TrackerConfig

T0 = datetime(2026, 1, 1, tzinfo=UTC)
CONFIG = TrackerConfig(distance_alarm_m=1609.344, elevation_alarm_deg=50.0, wait_updates=2)


def aircraft(distance_m: float, poll: int) -> Aircraft:
    return Aircraft(
        hex="a1b2c3",
        flight="TEST001",
        registration=None,
        aircraft_type=None,
        lat_deg=0.0,
        lon_deg=0.0,
        altitude_m=500.0,
        on_ground=False,
        ground_speed_m_per_s=100.0,
        track_deg=90.0,
        vertical_rate_m_per_s=None,
        squawk=None,
        rssi_db=None,
        seen_s=0.0,
        seen_pos_s=0.0,
        distance_m=distance_m,
        bearing_deg=0.0,
        elevation_deg=10.0,
        observed_at=T0 + timedelta(seconds=poll),
    )


def snapshots(*distances_m: float | None) -> list[Snapshot]:
    """One snapshot per entry; None is an empty sky."""
    return [
        Snapshot(T0 + timedelta(seconds=i), 0, () if d is None else (aircraft(d, i),))
        for i, d in enumerate(distances_m)
    ]


class FakeSource:
    def __init__(self, items):
        self.items = list(items)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_one_pass_reaches_every_sink():
    source = FakeSource(snapshots(5000.0, 800.0, 300.0, 5000.0, None))
    seen_a, seen_b, sleeps = [], [], []
    count = main.poll_loop(
        source,
        Tracker(CONFIG),
        [seen_a.append, seen_b.append],
        interval_s=0.5,
        sleep=sleeps.append,
        max_polls=5,
    )
    assert count == 1
    assert [p.sighting.closest.distance_m for p in seen_a] == [300.0]
    assert seen_b == seen_a
    assert all(isinstance(p, Post) and p.image_png is None for p in seen_a)
    assert sleeps == [0.5] * 5


def test_render_result_travels_with_the_post():
    source = FakeSource(snapshots(800.0, None, None))
    seen = []
    main.poll_loop(
        source,
        Tracker(CONFIG),
        [seen.append],
        0,
        render=lambda s: b"PNG" + s.closest.hex.encode(),
        sleep=lambda s: None,
        max_polls=3,
    )
    assert seen[0].image_png == b"PNGa1b2c3"
    assert seen[0].image_name == "20260101T000000Z_a1b2c3.png"


def test_when_idle_runs_only_with_nothing_tracked():
    source = FakeSource(snapshots(None, 800.0, 800.0, None, None, None))
    idle_polls = []
    tracker = Tracker(CONFIG)
    main.poll_loop(
        source,
        tracker,
        [],
        0,
        when_idle=lambda: idle_polls.append(source.calls),
        sleep=lambda s: None,
        max_polls=6,
    )
    # Poll 1 is empty; polls 2-3 track; polls 4-5 are misses still tracked; the
    # sighting completes on poll 5, so poll 5 and 6 are idle again.
    assert idle_polls == [1, 5, 6]


def test_repeated_snapshot_is_not_a_new_poll():
    same = snapshots(800.0)[0]
    # Same observed_at three times, then nothing: only one tracker update happens,
    # so the two misses needed to complete never accrue.
    source = FakeSource([same, same, same])
    seen = []
    main.poll_loop(source, Tracker(CONFIG), [seen.append], 0, sleep=lambda s: None, max_polls=3)
    assert seen == []


def test_fetch_failure_is_logged_and_skipped(caplog):
    good = snapshots(800.0, None, None)
    source = FakeSource([good[0], ConnectionError("boom"), good[1], good[2]])
    seen = []
    with caplog.at_level(logging.WARNING, logger="abovetustin"):
        count = main.poll_loop(
            source, Tracker(CONFIG), [seen.append], 0, sleep=lambda s: None, max_polls=4
        )
    assert count == 1
    assert "fetch failed: boom" in caplog.text


def test_failing_sink_does_not_stop_the_others(caplog):
    def bad(sighting):
        raise RuntimeError("no")

    seen = []
    source = FakeSource(snapshots(800.0, None, None))
    with caplog.at_level(logging.ERROR, logger="abovetustin"):
        main.poll_loop(
            source, Tracker(CONFIG), [bad, seen.append], 0, sleep=lambda s: None, max_polls=3
        )
    assert len(seen) == 1
    assert "sink" in caplog.text and "failed" in caplog.text


def test_tracking_and_sighting_are_logged(caplog):
    source = FakeSource(snapshots(800.0, None, None))
    with caplog.at_level(logging.INFO, logger="abovetustin"):
        main.poll_loop(source, Tracker(CONFIG), [], 0, sleep=lambda s: None, max_polls=3)
    messages = [r.getMessage() for r in caplog.records]
    assert messages[0].startswith("tracking TEST001: 0.5 mi away at 1,640 ft")
    assert messages[1].startswith("sighting TEST001: 0.5 mi away")


class TestCli:
    def test_missing_config_is_a_usage_error(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            main.main(["run", "--config", str(tmp_path / "none.toml"), "--dry-run"])
        assert exc.value.code == 2
        assert "no config file" in capsys.readouterr().err

    MINIMAL = (
        "[receiver]\nlatitude_deg = 1\nlongitude_deg = 2\n[tracker]\n"
        'distance_alarm = "1 mi"\nelevation_alarm_deg = 50\n'
    )

    def test_live_run_needs_a_bluesky_section(self, tmp_path, capsys):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL)
        with pytest.raises(SystemExit) as exc:
            main.main(["run", "--config", str(cfg)])
        assert exc.value.code == 2
        assert "no [bluesky] section" in capsys.readouterr().err

    def test_live_run_fails_fast_on_bad_login(self, tmp_path, capsys, monkeypatch):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL + '[bluesky]\nhandle = "a.b"\napp_password = "nope"\n')

        def refuse(self):
            raise RuntimeError("401 Unauthorized")

        monkeypatch.setattr(main.BlueskyPoster, "login", refuse)
        with pytest.raises(SystemExit) as exc:
            main.main(["run", "--config", str(cfg)])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "Bluesky login as a.b failed: 401 Unauthorized" in err
        assert "nope" not in err

    def test_compose_prints_the_logged_sightings(self, tmp_path, capsys):
        from abovetustin.post import Post
        from abovetustin.post.jsonl import JsonlLog
        from abovetustin.tracker import Sighting

        log_path = tmp_path / "s.jsonl"
        sighting = Sighting(aircraft(800.0, 0), T0, T0, 3)
        JsonlLog(log_path).post(Post(sighting, b"png"))
        cfg = tmp_path / "c.toml"
        cfg.write_text(
            self.MINIMAL
            + f'[log]\npath = "{log_path}"\n'
            + '[post]\ntemplate = "${flight} ${dist_mi} mi"\nhashtags = ["#ADSB"]\n'
        )
        assert main.main(["compose", "--config", str(cfg), "--last", "5"]) == 0
        out = capsys.readouterr().out
        assert out.startswith(
            "TEST001 0.5 mi #ADSB\n    [20 chars, image: 20260101T000000Z_a1b2c3.png]"
        )

    def test_check_reports_receiver_and_login(self, tmp_path, caplog, monkeypatch):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL + '[bluesky]\nhandle = "a.b"\napp_password = "p"\n')
        snap = snapshots(800.0)[0]
        monkeypatch.setattr(main.readsb, "fetch", lambda url, receiver, timeout_s: snap)
        monkeypatch.setattr(main.BlueskyPoster, "login", lambda self: "did:plc:x")
        with caplog.at_level(logging.INFO, logger="abovetustin"):
            assert main.main(["check", "--config", str(cfg)]) == 0
        assert "receiver: 1 aircraft with positions" in caplog.text
        assert "config ok" in caplog.text

    def test_check_fails_on_unreachable_receiver(self, tmp_path, caplog, monkeypatch):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL)

        def down(url, receiver, timeout_s):
            raise ConnectionError("refused")

        monkeypatch.setattr(main.readsb, "fetch", down)
        with caplog.at_level(logging.ERROR, logger="abovetustin"):
            assert main.main(["check", "--config", str(cfg)]) == 1
        assert "cannot read" in caplog.text and "refused" in caplog.text

    def test_check_fails_on_bad_login(self, tmp_path, caplog, monkeypatch):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL + '[bluesky]\nhandle = "a.b"\napp_password = "nope"\n')
        monkeypatch.setattr(
            main.readsb, "fetch", lambda url, receiver, timeout_s: snapshots(None)[0]
        )

        def refuse(self):
            raise RuntimeError("401")

        monkeypatch.setattr(main.BlueskyPoster, "login", refuse)
        with caplog.at_level(logging.ERROR, logger="abovetustin"):
            assert main.main(["check", "--config", str(cfg)]) == 1
        assert "login as a.b failed: 401" in caplog.text and "nope" not in caplog.text

    def test_compose_without_a_log(self, tmp_path, capsys):
        cfg = tmp_path / "c.toml"
        cfg.write_text(self.MINIMAL + f'[log]\npath = "{tmp_path / "none.jsonl"}"\n')
        assert main.main(["compose", "--config", str(cfg)]) == 1
        assert "no sighting log" in capsys.readouterr().err
