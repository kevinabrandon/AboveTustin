# AboveTustin

AboveTustin watches a local ADS-B receiver and, whenever an aircraft passes close
overhead, posts a short note and a map of its track.

It started in 2016 as a Raspberry Pi in a window in Tustin, California, tweeting
as [@AboveTustin](https://twitter.com/abovetustin), and ran for several years and
tens of thousands of posts before the services it depended on were retired one by
one. The name stays; the project is being rebuilt from the ground up.

> **Status, November 2026: rebuild in progress.** v2 does not run end to end yet;
> see the roadmap below. The last working v1 code is preserved at tag
> [`v1.0.0`](https://github.com/kevinabrandon/AboveTustin/tree/v1.0.0).

## How it works

The receiver (readsb) decodes the position reports that aircraft broadcast and
publishes them as JSON once a second. The bot polls that feed and applies one
rule, unchanged since 2016:

* An aircraft is **in the alarm zone** when it is closer than a configured
  distance *or* higher above the horizon than a configured elevation angle.
* While it is in the zone, remember its state at the **closest approach**.
* Once it has been out of the zone for a few consecutive polls, **post** the
  closest-approach sighting: callsign, distance, altitude, elevation, heading,
  speed, time, and a map image of the track.

The map image comes from [tar1090](https://github.com/wiedehopf/tar1090) through a
headless browser, so it looks like the map you already watch. It can be framed on a
fixed point near the receiver (the default, so posts don't all point at one spot),
on the receiver itself, on the aircraft at its closest approach, or fitted to the
whole track, with an optional receiver marker and distance rings. See
`config.example.toml`.

A v1 post looked like this:

```
#SKW4530 : 0.2 mi away @ 1600 ft and 59.7° frm hrzn, heading SW @ 132.3mi/h 20:02:31. #ProbablyLanding #AboveTustin #RaspberryPi #ADSB #dump1090
```

## What v2 changes

| | v1 (2016) | v2 |
|---|---|---|
| Receiver | dump1090-mutability on a Raspberry Pi 2 | [readsb](https://github.com/wiedehopf/readsb) + [tar1090](https://github.com/wiedehopf/tar1090) |
| Map image | PhantomJS driving the dump1090 web map | Playwright driving tar1090 in headless Chrome |
| Posts to | Twitter (v1.1 API) | Bluesky first, then X |
| Route lookup | FlightAware FlightXML3 | a free ADS-B database, later |
| Config | `config.ini` next to the code, secrets inside | TOML, with the receiver position and credentials outside the repo |
| Units | miles and feet throughout | SI internally, converted at the edges by [pint](https://pint.readthedocs.io/) |
| Code | a handful of Python 3.4 scripts | a Python 3.12 package with tests and CI |

## Roadmap

- [x] Project skeleton: Python 3.12 package, tests, CI
- [x] Geometry in SI units, with the unit convention enforced by tests
- [x] Aircraft model and readsb parser, with recorded fixtures
- [x] Alarm-zone tracker
- [x] Configuration, sighting log and a dry-run mode
- [ ] Default alarm zone tuned against real traffic
- [x] Map image of the track
- [x] Bluesky posts
- [x] Runs as a service and survives a reboot
- [ ] Route lookup: where it came from, where it is going
- [ ] X posts

## Running it

You need readsb and tar1090 serving `aircraft.json` (wiedehopf's install scripts
set both up on a Pi or any Linux box), Google Chrome for the map images, and a
Bluesky account with an app password.

```sh
uv sync
cp config.example.toml ~/.config/abovetustin/config.toml   # then set the receiver position
uv run abovetustin check              # config, receiver and login
uv run abovetustin run --dry-run      # log and render sightings, post nothing
uv run abovetustin run                # post them
```

`deploy/README.md` covers running it as a systemd service that starts at boot and
restarts on failure. `abovetustin compose` shows what recent sightings would post
as, for tuning the template and rules.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Pull requests are welcome; see `CONTRIBUTING.md` for the workflow and the unit
convention.

## Credits

Written by [Kevin Brandon](https://github.com/kevinabrandon), with contributions
to v1 from [John Wiseman](https://github.com/wiseman) (Virtual Radar Server
support, aircraft identification), [Joseph Prochazka](https://github.com/jprochazka)
(the [adsb-receiver](https://github.com/jprochazka/adsb-receiver) integration),
[Sergiusz Paprzycki](https://github.com/spaprzycki) (FlightAware route lookup) and
[Scott Schulz](https://github.com/Jestre) (screenshot cropping). The original `flightdata.py` grew out of
[martinohanlon/flightdata](https://github.com/martinohanlon/flightdata).

MIT licensed.
