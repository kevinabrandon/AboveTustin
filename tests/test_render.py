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

    def test_receiver_layers_named(self):
        assert "Site position" in tar1090.RECEIVER_LAYERS
        assert "Range rings" in tar1090.RECEIVER_LAYERS


def test_renderer_centre_is_snapped():
    r = tar1090.Tar1090Renderer(CONFIG, (33.7458, -117.8261))
    assert r.center == (33.7, -117.8)


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
            r.render("000000")
