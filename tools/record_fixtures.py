"""Record anonymised readsb snapshots for use as test fixtures.

Polls ``aircraft.json`` and appends one snapshot per line to a JSONL file.
Nothing is written as received. Each snapshot is scrubbed first so that the
fixture reveals neither where the receiver is nor which real flights it saw:

* Positions are translated by a constant offset so the receiver sits at the
  coordinates of Tustin, CA. The geometry (distances, bearings,
  elevations) is preserved to within the small distortion of a translation.
  Receiver-relative and other positional fields are dropped.
* Addresses and callsigns are replaced by deterministic synthetic ones and
  registrations are removed, so the traffic cannot be looked up in a flight
  history service. The ``~`` prefix that marks MLAT and TIS-B addresses is kept.
* Timestamps are shifted so the recording starts at a fixed instant.

The real receiver position is read from ``receiver.json`` next to
``aircraft.json`` and never written anywhere.

Usage::

    uv run python tools/record_fixtures.py tests/fixtures/readsb/NAME.jsonl \
        [--base-url http://localhost/tar1090/data] [--count 120] \
        [--interval-s 1] [--min-aircraft 1] [--max-wait-s 10800]

Snapshots with fewer than ``--min-aircraft`` positioned aircraft are skipped
without counting, so the tool can be left running through quiet skies.
Output goes to ``NAME.jsonl.partial`` and is renamed when the recording is
complete, so a half-written file is never mistaken for a fixture.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

TUSTIN_LAT_DEG = 33.7458
TUSTIN_LON_DEG = -117.8261
RECORDING_START_EPOCH_S = 1_767_225_600  # 2026-01-01T00:00:00Z

DROP_KEYS = {"r", "r_dst", "r_dir", "rr_lat", "rr_lon", "lastPosition"}


class Scrubber:
    def __init__(self, receiver_lat_deg: float, receiver_lon_deg: float) -> None:
        self.dlat_deg = TUSTIN_LAT_DEG - receiver_lat_deg
        self.dlon_deg = TUSTIN_LON_DEG - receiver_lon_deg
        self.hexes: dict[str, str] = {}
        self.flights: dict[str, str] = {}
        self.time_offset_s: float | None = None

    def snapshot(self, data: dict[str, Any]) -> dict[str, Any]:
        """Scrub one document. Call only for snapshots that will be written, so
        the rebased clock starts at the first one kept."""
        if self.time_offset_s is None:
            self.time_offset_s = RECORDING_START_EPOCH_S - float(data["now"])
        return {
            "now": round(float(data["now"]) + self.time_offset_s, 3),
            "messages": data.get("messages", 0),
            "aircraft": [self.aircraft(a) for a in data.get("aircraft", []) if "lat" in a],
        }

    def aircraft(self, entry: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in entry.items() if k not in DROP_KEYS and not _positional(k)}
        out["lat"] = round(entry["lat"] + self.dlat_deg, 6)
        out["lon"] = round(entry["lon"] + self.dlon_deg, 6)
        out["hex"] = self.synthetic_hex(entry["hex"])
        if "flight" in entry:
            out["flight"] = self.synthetic_flight(entry["flight"])
        return out

    def synthetic_hex(self, real: str) -> str:
        prefix = "~" if real.startswith("~") else ""
        if real not in self.hexes:
            self.hexes[real] = f"{prefix}{0xF00000 + len(self.hexes):06x}"
        return self.hexes[real]

    def synthetic_flight(self, real: str) -> str:
        if real not in self.flights:
            self.flights[real] = f"TEST{len(self.flights):03d}".ljust(8)
        return self.flights[real]


def _positional(key: str) -> bool:
    lowered = key.lower()
    return lowered not in ("lat", "lon") and ("lat" in lowered or "lon" in lowered)


def _get_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("out", type=Path)
    ap.add_argument("--base-url", default="http://localhost/tar1090/data")
    ap.add_argument("--count", type=int, default=120)
    ap.add_argument("--interval-s", type=float, default=1.0)
    ap.add_argument("--min-aircraft", type=int, default=1)
    ap.add_argument("--max-wait-s", type=float, default=3 * 3600)
    args = ap.parse_args(argv)

    receiver = _get_json(f"{args.base_url}/receiver.json")
    scrubber = Scrubber(float(receiver["lat"]), float(receiver["lon"]))

    written = 0
    deadline = time.monotonic() + args.max_wait_s
    last_now = None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    partial = args.out.with_suffix(args.out.suffix + ".partial")
    with partial.open("w") as f:
        while written < args.count and time.monotonic() < deadline:
            data = _get_json(f"{args.base_url}/aircraft.json")
            if data["now"] != last_now:
                last_now = data["now"]
                positioned = sum(1 for a in data.get("aircraft", []) if "lat" in a)
                if positioned >= args.min_aircraft:
                    snapshot = scrubber.snapshot(data)
                    f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")
                    f.flush()
                    written += 1
                    print(
                        f"\r{written}/{args.count} snapshots, {len(snapshot['aircraft'])} aircraft",
                        end="",
                        file=sys.stderr,
                    )
            time.sleep(args.interval_s)
    print(file=sys.stderr)
    if written:
        partial.rename(args.out)
        print(f"wrote {written} snapshots to {args.out}", file=sys.stderr)
        return 0
    partial.unlink()
    print("no traffic seen, nothing written", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
