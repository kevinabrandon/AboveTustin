# Contributing

## Setup

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

The map renderer drives Google Chrome through Playwright. With Chrome installed
nothing more is needed; otherwise run `uv run playwright install chromium` and set
`browser_channel = ""` in the config. The browser test is skipped unless
`ABOVETUSTIN_TAR1090_URL` points at a live tar1090.

## Workflow

Branch from `master`, keep each commit to one logical change, and open a pull
request. `master` is protected: CI has to pass and the change has to come
through a PR.

## Conventions

### Units

Inside the package, every plain float is in SI base units and its name says so:
`distance_m`, `seen_s`, `speed_m_per_s`. Feet, knots, miles and the like exist
only at the edges, in the readsb parser, the config loader and the post
renderer, and conversions there go through [pint](https://pint.readthedocs.io/)
rather than hand-typed factors. Angles are the one exception and stay in
degrees (`_deg`).

The full policy is the docstring of `src/abovetustin/units.py`. It is enforced
by `tests/test_conventions.py`, so a violation fails CI with a list of the
offending names.

### Privacy

The receiver is someone's home. Nothing in the repository may contain or imply
a real receiver position: the example config and the test fixtures use the
coordinates of Tustin, CA (33.7458, -117.8261), and real
coordinates and credentials live in a config file outside the repo.
