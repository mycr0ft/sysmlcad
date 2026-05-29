"""Bridge between sysmlpy Model/Part objects and the sysmlcad Shape IR.

Converts SysML v2 part definitions and usages into parametric CAD shapes
using a convention-based mapping:

- Parts with ``length``, ``width``, ``height`` attributes become ``Box``
- Parts with ``height``, ``radius`` attributes become ``Cylinder``
- Parts with ``radius`` (only) become ``Sphere``
- Parts with ``height``, ``radius1``, ``radius2`` become ``Cone``
- Parts with ``majorRadius``, ``minorRadius`` become ``Torus``
- Parts with an ``operator`` attribute (``"union"``, ``"difference"``,
  ``"intersection"``) become CSG operations over their child parts
- Parts with ``x``, ``y``, ``z`` attributes get wrapped in ``Translate``
- Part definitions with ``export_params`` metadata become ``Module``

Usage::

    import sysmlpy
    from sysmlcad.sysml_bridge import sysml_file_to_cad

    code = sysml_file_to_cad("model.sysml", backend="openscad")
    print(code)
"""

from __future__ import annotations

from typing import Any

import sysmlpy

from sysmlcad.expression import Parameter, _to_expression
from sysmlcad.ir import (
    Assembly,
    Box,
    Cone,
    Cylinder,
    Difference,
    Intersection,
    Module,
    Scale,
    Shape,
    Sphere,
    Torus,
    Translate,
    Union,
)


# ---------------------------------------------------------------------------
# Attribute-name sets that identify each primitive
# ---------------------------------------------------------------------------

_BOX_ATTRS = {"length", "width", "height"}
_CYLINDER_ATTRS = {"height", "radius"}
_SPHERE_ATTR = {"radius"}
_CONE_ATTRS = {"height", "radius1", "radius2"}
_TORUS_ATTRS = {"majorRadius", "minorRadius"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_attr_value(part: sysmlpy.usage.Usage, name: str) -> float | None:
    """Look up an attribute value on *part* by name.

    Returns ``None`` if the attribute does not exist or has no value.
    """
    for child in part.children:
        if getattr(child, "sysml_type", None) == "attribute" and child.name == name:
            try:
                return child.get_value()
            except Exception:
                return None
    return None


def _collect_attrs(
    part: sysmlpy.usage.Usage,
) -> dict[str, Any]:
    """Return a dict of all attribute-name → value for *part*.

    Both numeric (float) and string values are preserved.
    """
    result: dict[str, Any] = {}
    for child in part.children:
        if getattr(child, "sysml_type", None) == "attribute":
            try:
                val = child.get_value()
                if val is not None:
                    # pint Quantity: convert to mm and extract magnitude
                    if hasattr(val, "units") and hasattr(val, "to"):
                        try:
                            result[child.name] = float(val.to("mm").magnitude)
                        except Exception:
                            result[child.name] = float(val.magnitude)
                    else:
                        # Try numeric conversion; keep string if it fails
                        try:
                            result[child.name] = float(val)
                        except (ValueError, TypeError):
                            result[child.name] = val
            except Exception:
                pass
    return result


def _child_parts(part: sysmlpy.usage.Usage) -> list[sysmlpy.usage.Usage]:
    """Return direct child parts of *part* (not attributes)."""
    return [
        c for c in part.children
        if getattr(c, "sysml_type", None) == "part"
    ]


def _parent_parts(part: sysmlpy.usage.Usage) -> list[sysmlpy.usage.Usage]:
    """Walk up to find parent parts (skip attributes and non-parts)."""
    parts: list[sysmlpy.usage.Usage] = []
    p = part.parent
    while p is not None:
        if getattr(p, "sysml_type", None) == "part":
            parts.append(p)
        p = p.parent
    return parts


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def part_to_shape(part: sysmlpy.usage.Usage) -> Shape | None:
    """Convert a SysML Part/Usage node (and its children) to a Shape.

    The conversion logic:

    1. If the part has an ``operator`` attribute (``"union"`` /
       ``"difference"`` / ``"intersection"``), recursively convert its
       child parts as operands.
    2. If the part has a known set of dimension attributes, create a
       primitive shape.
    3. If neither applies, skip the part (return ``None``).

    Any resulting shape is wrapped in ``Translate`` if the part also has
    ``x`` / ``y`` / ``z`` attributes.

    CSG operands can declare an explicit ``role`` attribute:

    * ``role = "positive"`` — the shape being kept (required for difference)
    * ``role = "negative"`` — the shape being removed (difference only)

    If no roles are set, the first child is treated as positive and
    remaining children as negatives (order-based fallback).
    """
    attrs = _collect_attrs(part)

    # --- CSG operation (operator attribute on nested parts) ----------------
    operator = attrs.get("operator")
    if operator is not None and _child_parts(part):
        op = operator.lower()

        # Collect child shapes, noting their role if declared
        positives: list[Shape] = []
        negatives: list[Shape] = []
        unmarked: list[Shape] = []
        for c in _child_parts(part):
            c_attrs = _collect_attrs(c)
            role = c_attrs.get("role", "")
            shape = _part_to_shape_recursive(c)
            if shape is None:
                continue
            if role == "positive":
                positives.append(shape)
            elif role == "negative":
                # Oversize + nudge down to prevent CSG coplanar-face artifacts
                negatives.append(Translate(Scale(shape, 1.001), z=-0.01))
            else:
                unmarked.append(shape)

        # Build operands based on roles (fall back to position if unset)
        if op == "difference":
            if positives or negatives:
                # Explicit roles — union all positives, subtract all negatives
                if not positives:
                    return None
                pos = Union(positives) if len(positives) > 1 else positives[0]
                shape = Difference(pos, negatives) if negatives else pos
            else:
                # Order-based fallback: first = positive, rest = negatives
                if len(unmarked) < 2:
                    return unmarked[0] if unmarked else None
                shape = Difference(
                    unmarked[0],
                    [Translate(Scale(s, 1.001), z=-0.01) for s in unmarked[1:]],
                )
        elif op == "union":
            operands = positives + negatives + unmarked
            if len(operands) < 2:
                return operands[0] if operands else None
            shape = Union(operands)
        elif op == "intersection":
            operands = positives + negatives + unmarked
            if len(operands) < 2:
                return operands[0] if operands else None
            shape = Intersection(operands)
        else:
            return None

        shape.params["_sysml_name"] = part.name
        shape = _apply_translate(shape, attrs)
        return shape

    # --- Primitive shape ---------------------------------------------------
    shape = _match_primitive(attrs)
    if shape is not None:
        shape.params["_sysml_name"] = part.name
        shape = _apply_translate(shape, attrs)
        return shape

    # --- Not a convertible part --------------------------------------------
    return None


def _part_to_shape_recursive(part: sysmlpy.usage.Usage) -> Shape | None:
    """Recursively convert *part*, checking if it is itself a CSG
    parent with nested operands.  Used when a parent CSG node is
    collecting its child operands.
    """
    # If this child has its own operator, convert it as a CSG node
    # (the recursive case).
    attrs = _collect_attrs(part)
    operator = attrs.get("operator")
    if operator is not None and _child_parts(part):
        return part_to_shape(part)

    # Otherwise it's a leaf primitive.
    return part_to_shape(part)


def _apply_translate(shape: Shape, attrs: dict[str, float]) -> Shape:
    """Wrap *shape* in Translate if attrs contains x/y/z offsets."""
    x = attrs.get("x", 0)
    y = attrs.get("y", 0)
    z = attrs.get("z", 0)
    if x != 0 or y != 0 or z != 0:
        shape = Translate(shape, x=x, y=y, z=z)
    return shape


def _match_primitive(attrs: dict[str, Any]) -> Shape | None:
    """Try to match *attrs* to a known primitive by its required
    attribute-name set.  Returns the Shape or ``None``."""
    keys = set(attrs.keys())

    if _BOX_ATTRS.issubset(keys):
        return Box(attrs["length"], attrs["width"], attrs["height"])

    if _CYLINDER_ATTRS.issubset(keys):
        return Cylinder(attrs["height"], attrs["radius"])

    if _CONE_ATTRS.issubset(keys):
        return Cone(attrs["height"], attrs["radius1"], attrs["radius2"])

    if _TORUS_ATTRS.issubset(keys):
        return Torus(attrs["majorRadius"], attrs["minorRadius"])

    # Sphere checked last (radius appears in Cylinder too)
    if _SPHERE_ATTR.issubset(keys) and len(keys) == 1:
        return Sphere(attrs["radius"])

    return None


# ---------------------------------------------------------------------------
# Model-level conversion
# ---------------------------------------------------------------------------

def model_to_shapes(model: sysmlpy.definition.Model) -> list[Shape]:
    """Convert top-level part usages in *model* to Shape IR objects.

    Returns a list of shapes (one per top-level convertible part).
    """
    results: list[Shape] = []
    for pkg in model.packages:
        for part in pkg.parts:
            if part.is_definition:
                continue
            shape = part_to_shape(part)
            if shape is not None:
                results.append(shape)
    return results


def model_to_assembly(model: sysmlpy.definition.Model) -> Assembly | None:
    """Convert the entire model to a single ``Assembly``.

    Returns ``None`` if no convertible parts are found.
    """
    shapes = model_to_shapes(model)
    if not shapes:
        return None
    assembly = Assembly(name=model.name)
    for shape in shapes:
        assembly.place(shape)
    return assembly


# ---------------------------------------------------------------------------
# Bridge: .sysml file → shape → export
# ---------------------------------------------------------------------------

def sysml_to_cad(
    source: str,
    backend: str = "openscad",
    **options,
) -> str:
    """Parse a SysML v2 source string and export CAD code.

    Parameters
    ----------
    source : str
        SysML v2 text (e.g. the contents of a ``.sysml`` file).
    backend : str
        CAD backend name (``"openscad"``, ``"build123d"``, …).
    **options :
        Forwarded to the backend's ``render()`` method.

    Returns
    -------
    str
        Generated CAD source code.
    """
    import sysmlpy
    from sysmlcad import export as _export

    model = sysmlpy.loads(source)
    assembly = model_to_assembly(model)
    if assembly is None:
        return ""
    return _export(assembly, backend=backend, **options)


def sysml_file_to_cad(
    path: str,
    backend: str = "openscad",
    **options,
) -> str:
    """Read a ``.sysml`` file and export CAD code.

    Convenience wrapper around :func:`sysml_to_cad`.
    """
    import pathlib

    source = pathlib.Path(path).read_text(encoding="utf-8")
    return sysml_to_cad(source, backend=backend, **options)
