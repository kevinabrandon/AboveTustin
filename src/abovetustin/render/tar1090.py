"""Map images from tar1090, through a headless browser.

tar1090 already draws the map, the aircraft and their trails, so the
renderer keeps one browser page open on it and, when a sighting completes,
selects that aircraft and takes a screenshot. The page stays open between
sightings because that is where the trail history lives: readsb's JSON only
carries current positions, and tar1090 accumulates the track in the page as
the aircraft is watched.

The page is opened with the receiver's range rings and range outline
switched off, the layer with the receiver marker is hidden, and the info
panel (which prints the aircraft's distance from the receiver) is
suppressed; ``show_receiver = true`` puts the marker and rings back, at
``ring_distances``.

``center`` chooses the framing of each image:

* ``grid``: the receiver position snapped to a ``grid_deg`` grid. The
  default, because the centres of many posts then cluster on a grid point
  rather than on the receiver.
* ``receiver``: the receiver itself.
* ``aircraft``: the aircraft at its closest approach.
* ``track``: the whole trail, fitted to the frame, zoomed in no further
  than ``zoom``.

``labels`` and ``label_detail`` are tar1090's L and O keys: labels on or
off, and how many times O was pressed (0 to 3) to extend them with
registration, type, speed, altitude and callsign.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from abovetustin import units
from abovetustin.geomath import LatLonDeg

log = logging.getLogger(__name__)

#: tar1090 layer titles that reveal where the receiver is.
RECEIVER_LAYERS = ("Site position", "Range rings", "actual range outline")

_HIDE_LAYERS_JS = """(titles) => OLMap.getLayers().getArray().forEach(layer => {
    if (titles.includes(layer.get('title'))) layer.setVisible(false);
})"""
_SHOW_LAYERS_JS = """(titles) => OLMap.getLayers().getArray().forEach(layer => {
    if (titles.includes(layer.get('title'))) layer.setVisible(true);
})"""
# Rings are drawn in tar1090's display units; switch the page to statute
# miles so the ring labels read like the posts do.
_DRAW_RINGS_JS = """(miles) => {
    DisplayUnits = 'imperial';
    SiteCircles = true;
    SiteCirclesDistances = miles;
    SiteCirclesColors = ['#444444'];
    SiteCirclesLineDash = [6, 6];
    drawSiteCircle();
}"""
_HIDE_PANELS_CSS = "#selected_infoblock, #sidebar_container { display: none !important; }"
_SELECT_JS = """(hex) => {
    if (!g.planes[hex]) return false;
    selectPlaneByHex(hex, {noDeselect: true});
    return true;
}"""
_CENTER_JS = """([lat, lon, zoom]) => {
    OLMap.getView().setCenter(ol.proj.fromLonLat([lon, lat]));
    OLMap.getView().setZoom(zoom);
}"""
# Fit the view to the selected aircraft's trail; fall back to centring on
# the aircraft when there is no trail to fit.
_FIT_TRACK_JS = """([hex, lat, lon, zoom, pad]) => {
    const segs = (g.planes[hex].track_linesegs || []).filter(s => s.fixed);
    if (segs.length === 0) {
        OLMap.getView().setCenter(ol.proj.fromLonLat([lon, lat]));
        OLMap.getView().setZoom(zoom);
        return 0;
    }
    const here = ol.proj.fromLonLat([lon, lat]);
    let extent = [here[0], here[1], here[0], here[1]];
    segs.forEach(s => {
        const e = s.fixed.getExtent();
        extent = [Math.min(extent[0], e[0]), Math.min(extent[1], e[1]),
                  Math.max(extent[2], e[2]), Math.max(extent[3], e[3])];
    });
    OLMap.getView().fit(extent, {padding: [pad, pad, pad, pad], maxZoom: zoom});
    return segs.length;
}"""
_DESELECT_JS = "() => deselectAllPlanes()"


class RenderError(Exception):
    pass


CENTER_MODES = ("grid", "receiver", "aircraft", "track")
#: Pixels between the fitted track and the frame edge in "track" mode.
TRACK_PADDING_PX = 60
DEFAULT_RING_DISTANCES_M = tuple(units.parse(f"{n} mi", "m") for n in (1, 2, 5))


@dataclass(frozen=True, slots=True)
class RenderConfig:
    #: The tar1090 page, e.g. ``http://localhost/tar1090/``.
    url: str
    zoom: int = 11
    width_px: int = 1280
    height_px: int = 720
    #: One of CENTER_MODES; see the module docstring.
    center: str = "grid"
    grid_deg: float = 0.1
    #: Draw tar1090's receiver marker and range rings.
    show_receiver: bool = False
    ring_distances_m: tuple[float, ...] = DEFAULT_RING_DISTANCES_M
    #: Playwright browser channel: "chrome", "msedge", or "" for its own chromium.
    browser_channel: str = "chrome"
    #: Reload the page this often, when nothing is being tracked, to keep its memory in check.
    reload_after_s: float = 3600.0
    #: Aircraft labels on the map (tar1090's L key) and their detail level (the O key, 0-3).
    labels: bool = False
    label_detail: int = 0


def snap(position: LatLonDeg, grid_deg: float) -> LatLonDeg:
    """``position`` moved to the nearest point of a ``grid_deg`` grid."""
    return (
        round(round(position[0] / grid_deg) * grid_deg, 6),
        round(round(position[1] / grid_deg) * grid_deg, 6),
    )


def map_center(config: RenderConfig, receiver: LatLonDeg) -> LatLonDeg:
    """Where the page is centred when it opens, and the fixed centre for the
    ``grid`` and ``receiver`` modes. The aircraft-relative modes reframe per
    image and start from the grid point."""
    if config.center == "receiver":
        return receiver
    if config.center in CENTER_MODES:
        return snap(receiver, config.grid_deg)
    raise ValueError(f"center must be one of {CENTER_MODES}, not {config.center!r}")


def ring_distances_mi(config: RenderConfig) -> list[float]:
    """Ring radii in statute miles, which is how tar1090 is told to draw them."""
    return [units.Quantity(d_m, "m").to("mi").magnitude for d_m in config.ring_distances_m]


def page_url(config: RenderConfig, center: LatLonDeg) -> str:
    """The tar1090 URL the renderer opens: centred and quiet. The receiver's
    rings and outline are off here and turned back on after load when asked."""
    params = {
        "lat": f"{center[0]:.4f}",
        "lon": f"{center[1]:.4f}",
        "zoom": config.zoom,
        "rangeRings": 0,
        "outlineWidth": 0,
        "mapDim": 0,
    }
    flags = ["hideSidebar", "hideButtons", "noVanish"]
    if config.labels:
        flags.append("enableLabels")
        params["extendedLabels"] = config.label_detail
    return f"{config.url}?{urlencode(params)}&{'&'.join(flags)}"


class Tar1090Renderer:
    """Keeps a browser page open on tar1090 and screenshots selected aircraft.

    Use as a context manager. ``render`` raises :class:`RenderError` when the
    aircraft is not on the map or the browser has gone away; the caller
    decides whether a post goes out without an image.
    """

    def __init__(self, config: RenderConfig, receiver: LatLonDeg) -> None:
        self.config = config
        self.center = map_center(config, receiver)
        self._playwright = None
        self._browser = None
        self._page = None
        self._opened_at = 0.0

    def __enter__(self) -> Tar1090Renderer:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
            self._page = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def _open(self) -> None:
        assert self._playwright is not None
        launch: dict[str, object] = {"headless": True}
        if self.config.browser_channel:
            launch["channel"] = self.config.browser_channel
        self._browser = self._playwright.chromium.launch(**launch)
        self._page = self._browser.new_page(
            viewport={"width": self.config.width_px, "height": self.config.height_px}
        )
        self._page.goto(
            page_url(self.config, self.center), wait_until="networkidle", timeout=60_000
        )
        self._page.evaluate(_HIDE_LAYERS_JS, list(RECEIVER_LAYERS))
        if self.config.show_receiver:
            self._page.evaluate(_SHOW_LAYERS_JS, ["Site position", "Range rings"])
            self._page.evaluate(_DRAW_RINGS_JS, ring_distances_mi(self.config))
        self._page.add_style_tag(content=_HIDE_PANELS_CSS)
        self._opened_at = time.monotonic()
        log.info("tar1090 page open at %s", page_url(self.config, self.center))

    def reload_if_stale(self) -> None:
        """Reopen the page if it has been up longer than ``reload_after_s``.
        Call only when nothing is being tracked: the trails are lost."""
        if time.monotonic() - self._opened_at >= self.config.reload_after_s:
            log.info("reloading the tar1090 page")
            if self._browser is not None:
                self._browser.close()
            self._open()

    def render(self, hex_code: str, position: LatLonDeg) -> bytes:
        """PNG of the map with ``hex_code`` selected and its trail shown,
        framed per ``config.center``. ``position`` is the aircraft's
        closest-approach position."""
        if self._page is None:
            raise RenderError("renderer is not open")
        try:
            if not self._page.evaluate(_SELECT_JS, hex_code):
                raise RenderError(f"{hex_code} is not on the map")
            self._frame(hex_code, position)
            self._page.wait_for_timeout(1500)
            png = self._page.screenshot(type="png")
            self._page.evaluate(_DESELECT_JS)
        except RenderError:
            raise
        except Exception as exc:  # Playwright errors: browser gone, page crashed
            raise RenderError(f"browser failure: {exc}") from exc
        return png

    def _frame(self, hex_code: str, position: LatLonDeg) -> None:
        assert self._page is not None
        zoom = self.config.zoom
        if self.config.center == "track":
            self._page.evaluate(
                _FIT_TRACK_JS, [hex_code, position[0], position[1], zoom, TRACK_PADDING_PX]
            )
        elif self.config.center == "aircraft":
            self._page.evaluate(_CENTER_JS, [position[0], position[1], zoom])
        else:
            self._page.evaluate(_CENTER_JS, [self.center[0], self.center[1], zoom])
