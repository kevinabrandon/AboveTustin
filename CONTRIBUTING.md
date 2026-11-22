# Contributing

## Setup

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

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
original v1 location in Tustin, CA (33.754271, -117.823096), and real
coordinates and credentials live in a config file outside the repo.
