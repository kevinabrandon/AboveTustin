import os

import pytest

from abovetustin.render import tar1090

CONFIG = tar1090.RenderConfig(url="http://localhost/tar1090/", zoom=11, grid_deg=0.1)


class TestSnap:
    @pytest.mark.parametrize(
        ("position", "expected"),
        [
            ((33.7458, -117.8261), (33.7, -117.8)),
            ((33.76, -117.86), (33.8, -117.9)),
            ((33.75, -117.85), (33.8, -117.8)),  # round half to even, like Python
            ((0.0, 0.0), (0.0, 0.0)),
        ],
    )
    def test_to_tenth_of_a_degree(self, position, expected):
        assert tar1090.snap(position, 0.1) == expected

    def test_finer_grid(self):
        assert tar1090.snap((33.7458, -117.8261), 0.01) == (33.75, -117.83)

    def test_result_is_never_the_input_unless_on_grid(self):
        assert tar1090.snap((33.7458, -117.8261), 0.1) != (33.7458, -117.8261)


class TestPageUrl:
    def test_centre_zoom_and_privacy_flags(self):
        url = tar1090.page_url(CONFIG, (33.7, -117.8))
        assert url.startswith("http://localhost/tar1090/?")
        assert "lat=33.7000" in url and "lon=-117.8000" in url and "zoom=11" in url
        assert "rangeRings=0" in url and "outlineWidth=0" in url
        for flag in ("hideSidebar", "hideButtons", "noVanish"):
            assert flag in url

    def test_labels_off_by_default(self):
        url = tar1090.page_url(CONFIG, (33.7, -117.8))
        assert "enableLabels" not in url and "extendedLabels" not in url

    def test_labels_with_detail(self):
        config = tar1090.RenderConfig(url=CONFIG.url, labels=True, label_detail=2)
        url = tar1090.page_url(config, (33.7, -117.8))
        assert "enableLabels" in url and "extendedLabels=2" in url

    def test_receiver_layers_named(self):
        assert "Site position" in tar1090.RECEIVER_LAYERS
        assert "Range rings" in tar1090.RECEIVER_LAYERS


class TestCentreAndRings:
    def test_grid_centre_is_snapped(self):
        r = tar1090.Tar1090Renderer(CONFIG, (33.7458, -117.8261))
        assert r.center == (33.7, -117.8)

    def test_receiver_centre_is_exact(self):
        config = tar1090.RenderConfig(url=CONFIG.url, center="receiver")
        assert tar1090.Tar1090Renderer(config, (33.7458, -117.8261)).center == (33.7458, -117.8261)

    @pytest.mark.parametrize("mode", ["aircraft", "track"])
    def test_aircraft_relative_modes_open_on_the_grid_point(self, mode):
        config = tar1090.RenderConfig(url=CONFIG.url, center=mode)
        assert tar1090.Tar1090Renderer(config, (33.7458, -117.8261)).center == (33.7, -117.8)

    def test_unknown_centre_is_rejected(self):
        with pytest.raises(ValueError, match="center must be one of"):
            tar1090.map_center(tar1090.RenderConfig(url=CONFIG.url, center="house"), (0.0, 0.0))

    def test_default_rings_are_one_two_five_miles(self):
        assert tar1090.ring_distances_mi(CONFIG) == pytest.approx([1.0, 2.0, 5.0])

    def test_rings_convert_from_si(self):
        config = tar1090.RenderConfig(url=CONFIG.url, ring_distances_m=(1609.344, 8046.72))
        assert tar1090.ring_distances_mi(config) == pytest.approx([1.0, 5.0])


class FakePage:
    """Records the scripts render() runs, in place of a browser page."""

    def __init__(self, planes=("a1b2c3",)):
        self.planes = set(planes)
        self.calls: list[tuple[str, object]] = []

    def evaluate(self, script, arg=None):
        self.calls.append((script, arg))
        if script is tar1090._SELECT_JS:
            return arg in self.planes
        return None

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self, type="png"):
        return b"\x89PNG-fake"


def renderer_with_fake_page(**overrides):
    config = tar1090.RenderConfig(url=CONFIG.url, zoom=11, **overrides)
    r = tar1090.Tar1090Renderer(config, (33.7458, -117.8261))
    r._page = FakePage()
    return r, r._page


class TestFraming:
    POSITION = (33.76, -117.80)

    def test_grid_mode_centres_on_the_grid_point(self):
        r, page = renderer_with_fake_page(center="grid")
        assert r.render("a1b2c3", self.POSITION) == b"\x89PNG-fake"
        assert (tar1090._CENTER_JS, [33.7, -117.8, 11]) in page.calls

    def test_receiver_mode_centres_on_the_receiver(self):
        r, page = renderer_with_fake_page(center="receiver")
        r.render("a1b2c3", self.POSITION)
        assert (tar1090._CENTER_JS, [33.7458, -117.8261, 11]) in page.calls

    def test_aircraft_mode_centres_on_the_closest_approach(self):
        r, page = renderer_with_fake_page(center="aircraft")
        r.render("a1b2c3", self.POSITION)
        assert (tar1090._CENTER_JS, [33.76, -117.8, 11]) in page.calls

    def test_track_mode_fits_the_trail_capped_at_zoom(self):
        r, page = renderer_with_fake_page(center="track")
        r.render("a1b2c3", self.POSITION)
        assert (
            tar1090._FIT_TRACK_JS,
            ["a1b2c3", 33.76, -117.8, 11, tar1090.TRACK_PADDING_PX],
        ) in page.calls
        assert not any(script is tar1090._CENTER_JS for script, _ in page.calls)

    def test_selects_then_frames_then_deselects(self):
        r, page = renderer_with_fake_page(center="grid")
        r.render("a1b2c3", self.POSITION)
        scripts = [script for script, _ in page.calls]
        assert scripts == [tar1090._SELECT_JS, tar1090._CENTER_JS, tar1090._DESELECT_JS]

    def test_unknown_aircraft(self):
        r, page = renderer_with_fake_page()
        with pytest.raises(tar1090.RenderError, match="not on the map"):
            r.render("000000", self.POSITION)
        assert len(page.calls) == 1

    def test_browser_failure_is_a_render_error(self):
        r, page = renderer_with_fake_page()
        page.screenshot = lambda type="png": (_ for _ in ()).throw(RuntimeError("gone"))
        with pytest.raises(tar1090.RenderError, match="browser failure: gone"):
            r.render("a1b2c3", self.POSITION)


@pytest.mark.skipif(
    not os.environ.get("ABOVETUSTIN_TAR1090_URL"),
    reason="set ABOVETUSTIN_TAR1090_URL to a live tar1090 to run the browser test",
)
def test_live_page_opens_and_hides_receiver_layers():
    from abovetustin.render.tar1090 import Tar1090Renderer

    config = tar1090.RenderConfig(url=os.environ["ABOVETUSTIN_TAR1090_URL"])
    with Tar1090Renderer(config, (33.7458, -117.8261)) as r:
        hidden = r._page.evaluate(
            "(t) => OLMap.getLayers().getArray().filter(l => t.includes(l.get('title')))"
            ".map(l => l.getVisible())",
            list(tar1090.RECEIVER_LAYERS),
        )
        assert hidden and not any(hidden)
        with pytest.raises(tar1090.RenderError, match="not on the map"):
            r.render("000000", (33.7458, -117.8261))
