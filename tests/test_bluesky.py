from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from abovetustin.aircraft import Aircraft
from abovetustin.post import Post, bluesky
from abovetustin.post.template import PostConfig, Rule
from abovetustin.tracker import Sighting

T0 = datetime(2026, 1, 2, 4, 2, 31, tzinfo=UTC)
CLOSEST = Aircraft(
    hex="a1b2c3",
    flight="SKW4530",
    registration=None,
    aircraft_type=None,
    lat_deg=33.75,
    lon_deg=-117.82,
    altitude_m=487.68,
    on_ground=False,
    ground_speed_m_per_s=59.14,
    track_deg=225.0,
    vertical_rate_m_per_s=None,
    squawk=None,
    rssi_db=None,
    seen_s=0.0,
    seen_pos_s=0.0,
    distance_m=321.87,
    bearing_deg=190.0,
    elevation_deg=59.7,
    observed_at=T0,
)
SIGHTING = Sighting(CLOSEST, T0 - timedelta(seconds=12), T0 + timedelta(seconds=9), 22)
POST_CONFIG = PostConfig(
    template="${flight}: ${dist_mi} mi away at ${alt_ft} ft, ${time}",
    hashtags=("#ADSB",),
    rules=(Rule(tag="#ProbablyLanding", altitude_max_m=762.0),),
    tz=ZoneInfo("America/Los_Angeles"),
)


class TestRichText:
    def test_hashtags_become_tag_facets_and_text_is_preserved(self):
        builder = bluesky.rich_text("SKW4530 over the house #ProbablyLanding #ADSB, done")
        assert builder.build_text() == "SKW4530 over the house #ProbablyLanding #ADSB, done"
        facets = builder.build_facets()
        # "#ADSB," is not a tag because of the trailing comma; v1 never emitted those.
        assert [f.features[0].tag for f in facets] == ["ProbablyLanding"]

    def test_lone_hash_and_all_digit_tags_are_text(self):
        assert bluesky.rich_text("# 1 #2 #22").build_facets() == []
        tags = [
            f.features[0].tag for f in bluesky.rich_text("#x1 #2CloseForComfort").build_facets()
        ]
        assert tags == ["x1", "2CloseForComfort"]


class FakeClient:
    def __init__(self, service):
        self.service = service
        self.calls = []

    def login(self, handle, password):
        self.calls.append(("login", handle, password))

        class Profile:
            did = "did:plc:fake"

        return Profile()

    def send_image(self, text, image, image_alt):
        self.calls.append(("send_image", text.build_text(), image, image_alt))

    def send_post(self, text):
        self.calls.append(("send_post", text.build_text()))


def make_poster():
    clients = []

    def factory(service):
        client = FakeClient(service)
        clients.append(client)
        return client

    config = bluesky.BlueskyConfig(handle="above.example.com", app_password="xxxx-xxxx")
    return bluesky.BlueskyPoster(config, POST_CONFIG, client_factory=factory), clients


def test_login_uses_handle_and_app_password():
    poster, clients = make_poster()
    assert poster.login() == "did:plc:fake"
    assert clients[0].service == "https://bsky.social"
    assert clients[0].calls == [("login", "above.example.com", "xxxx-xxxx")]


def test_post_with_image_attaches_it_with_summary_alt_text():
    poster, clients = make_poster()
    poster.post(Post(SIGHTING, b"\x89PNG"))
    kind, text, image, alt = clients[0].calls[-1]
    assert kind == "send_image"
    assert text == "SKW4530: 0.2 mi away at 1600 ft, 20:02:31 #ProbablyLanding #ADSB"
    assert image == b"\x89PNG"
    assert alt.startswith("SKW4530: 0.2 mi away at 1,600 ft, 59.7° above the horizon")


def test_post_without_image_is_text_only_and_logs_in_once():
    poster, clients = make_poster()
    poster.post(Post(SIGHTING))
    poster.post(Post(replace(SIGHTING, samples=1)))
    kinds = [c[0] for c in clients[0].calls]
    assert kinds == ["login", "send_post", "send_post"]
    assert len(clients) == 1
