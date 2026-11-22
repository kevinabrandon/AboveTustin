"""Unit policy: pint at the boundaries, SI floats inside.

The receiver reports feet and knots, the posts read in miles and mph, and
the config says whatever the operator wrote. All of that is boundary.
Inside the package every plain float is in SI base units (m, s, m/s) and
its name carries the unit as a suffix: ``distance_m``, ``seen_s``,
``speed_m_per_s``. The suffix is the units contract where the type system
cannot be.

Rules, enforced by ``tests/test_conventions.py``:

1. Float parameters, dataclass fields and module constants carry a unit
   suffix. Non-SI suffixes (``_ft``, ``_kt``, ``_mi``, ...) may appear only
   in boundary modules: this one, ``config.py``, ``source/``, ``post/`` and
   ``render/``.
2. No unit conversion factor appears anywhere but here. Conversions go
   through pint so dimensions are checked rather than assumed.
3. ``pint`` is imported only here, and this module is imported only by the
   boundary modules. Display conversions build a ``Quantity`` from the SI
   float and call ``.to()``; there is no float-to-float helper because its
   magnitude argument could not carry a unit suffix.

The one exception: angles are degrees (``_deg``), not radians. Every
producer and consumer of a bearing or elevation speaks degrees and there
is a single ``atan2`` between them.
"""

from __future__ import annotations

import pint

ureg = pint.UnitRegistry()
Quantity = ureg.Quantity


def si(quantity: pint.Quantity) -> float:
    """Magnitude of ``quantity`` in SI base units."""
    return float(quantity.to_base_units().magnitude)


def parse(text: str, like: str) -> float:
    """Parse a quantity such as ``"1.2 mi"`` and return its SI magnitude.

    ``like`` is a unit the text must be compatible with (``"m"``, ``"m/s"``).
    A bare number or a quantity of the wrong dimension raises
    ``pint.DimensionalityError``.
    """
    return si(ureg.Quantity(text).to(like))


# Factors the readsb parser needs, evaluated by pint once at import so the
# per-poll loop multiplies plain floats. They are the only place a parser
# may get a factor from.
_M_PER_FT = si(Quantity(1, "foot"))
_M_PER_S_PER_KT = si(Quantity(1, "knot"))
_M_PER_S_PER_FT_PER_MIN = si(Quantity(1, "foot/minute"))


def m_from_ft(length_ft: float) -> float:
    return length_ft * _M_PER_FT


def m_per_s_from_kt(speed_kt: float) -> float:
    return speed_kt * _M_PER_S_PER_KT


def m_per_s_from_ft_per_min(rate_ft_per_min: float) -> float:
    return rate_ft_per_min * _M_PER_S_PER_FT_PER_MIN
