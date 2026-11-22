"""Enforce the unit policy described in ``abovetustin.units``.

These are tests rather than prose so that a contributor who breaks the
policy hears about it from CI, not from a reviewer. Each test collects every
violation in the package before failing, so the message lists them all.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "abovetustin"

# Modules that talk to the outside world. Only these may import pint or
# ``abovetustin.units`` and only these may name a value in a non-SI unit.
BOUNDARY = ("units.py", "config.py", "source/", "post/", "render/")

SI_SUFFIXES = ("_m", "_s", "_m_per_s", "_deg", "_db")
NON_SI_SUFFIXES = ("_ft", "_mi", "_km", "_nm", "_kt", "_mph", "_ft_per_min", "_ms")
DIMENSIONLESS_SUFFIXES = ("_ratio", "_fraction")

# Any numeric literal within 0.1 % of one of these values, or of its
# reciprocal, is a unit conversion written by hand.
CONVERSION_FACTORS = {
    "metres per foot": 0.3048,
    "metres per statute mile": 1609.344,
    "kilometres per statute mile": 1.609344,
    "metres per nautical mile": 1852.0,
    "metres per second per knot": 0.514444,
    "mph per knot": 1.15078,
    "nautical miles per statute mile": 0.868976,
    "feet per statute mile": 5280.0,
    "feet per nautical mile": 6076.12,
    "mph per metre per second": 2.23694,
    "knots per metre per second": 1.94384,
}


def _modules() -> list[tuple[str, ast.Module]]:
    out = []
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE).as_posix()
        out.append((rel, ast.parse(path.read_text(), filename=rel)))
    return out


def _is_boundary(rel: str) -> bool:
    return rel.startswith(BOUNDARY)


def _mentions_float(annotation: ast.expr | None) -> bool:
    return annotation is not None and "float" in ast.unparse(annotation)


def _suffix_ok(name: str, rel: str) -> bool:
    name = name.lower()  # constants are UPPER_CASE
    if name.endswith(SI_SUFFIXES) or name.endswith(DIMENSIONLESS_SUFFIXES):
        return True
    return _is_boundary(rel) and name.endswith(NON_SI_SUFFIXES)


def test_float_names_carry_a_unit_suffix():
    """Rule 1: float parameters, dataclass fields and numeric module constants
    are named with their unit."""
    violations = []
    for rel, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                args = node.args
                for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                    if _mentions_float(arg.annotation) and not _suffix_ok(arg.arg, rel):
                        violations.append(f"{rel}:{arg.lineno} parameter {arg.arg!r}")
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if (
                        isinstance(item, ast.AnnAssign)
                        and isinstance(item.target, ast.Name)
                        and _mentions_float(item.annotation)
                        and not _suffix_ok(item.target.id, rel)
                    ):
                        violations.append(f"{rel}:{item.lineno} field {item.target.id!r}")
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
                value = node.value
            else:
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, float):
                for t in targets:
                    if not _suffix_ok(t.id, rel):
                        violations.append(f"{rel}:{node.lineno} constant {t.id!r}")
    assert not violations, "float names without a unit suffix:\n  " + "\n  ".join(violations)


def test_no_hand_written_conversion_factors():
    """Rule 2: conversion factors live in pint, not in the code."""
    violations = []
    for rel, tree in _modules():
        if rel == "units.py":
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, int | float)):
                continue
            value = float(node.value)
            if value == 0.0 or isinstance(node.value, bool):
                continue
            for name, factor in CONVERSION_FACTORS.items():
                for candidate in (factor, 1.0 / factor):
                    if abs(value - candidate) <= candidate * 1e-3:
                        violations.append(f"{rel}:{node.lineno} {node.value} looks like {name}")
    assert not violations, "hand-written unit conversions:\n  " + "\n  ".join(violations)


def test_pint_and_units_stay_at_the_boundary():
    """Rule 3: pint is imported only by units.py, and units.py only by
    boundary modules."""
    violations = []
    for rel, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [
                    f"{node.module or ''}.{a.name}".strip(".") for a in node.names
                ]
                if node.level:  # relative import: resolve against the package
                    names = ["abovetustin." + n if n else "abovetustin" for n in names]
            else:
                continue
            for name in names:
                if (name == "pint" or name.startswith("pint.")) and rel != "units.py":
                    violations.append(f"{rel}:{node.lineno} imports pint")
                if name == "abovetustin.units" and not _is_boundary(rel):
                    violations.append(f"{rel}:{node.lineno} imports abovetustin.units")
    assert not violations, "units used outside the boundary:\n  " + "\n  ".join(violations)
