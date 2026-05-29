"""Shape Intermediate Representation (IR) for parametric CAD models.

A shape-construction API that is backend-agnostic.  Supports:

- Primitives:  Box, Cylinder, Sphere, Cone, Torus, Wedge, Prism
- 2D profiles: Polygon, Circle, Rectangle, Text
- 2D->3D ops:  Extrude, Revolve, Loft, Sweep
- Transforms:  Translate, Rotate, Scale, Mirror
- CSG:         Union, Difference, Intersection
- Assembly:    Assembly (named child placements), Connection

Operator overloads for a natural Python DSL:
    box = Box(10, 20, 30)
    cyl = Cylinder(30, 5)
    result = box - cyl            # Difference
    assembly = box + cyl          # Union
"""

from __future__ import annotations

from typing import Any

from sysmlcad.expression import (
    Expression,
    Literal,
    ParameterRef,
    Parameter,
    _to_expression,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_dim(value: Any) -> Expression:
    """Convert a dimension value into an Expression.

    Accepts: float, int, pint.Quantity, Expression, Parameter, str.

    ``Parameter`` objects are kept as-is so that ``evaluate_params()``
    can resolve their default value.  ``ParameterRef`` is only created
    when a ``Parameter`` appears *inside* an arithmetic expression
    (e.g. ``Parameter("x", 10) * 2``).
    """
    if isinstance(value, Expression):
        return value
    if isinstance(value, Parameter):
        return value
    if isinstance(value, str):
        return ParameterRef(value)
    return Literal(value)


def _resolve_dims(*values: Any) -> list[Expression]:
    return [_resolve_dim(v) for v in values]


# ---------------------------------------------------------------------------
# Shape base
# ---------------------------------------------------------------------------

class Shape:
    """Base class for all shapes in the IR."""

    type = "Shape"

    def __init__(self, name: str | None = None):
        self._name = name
        self.params: dict[str, Any] = {}
        self.children: list[Shape] = []
        self.parent: Shape | None = None

    @property
    def name(self) -> str:
        if self._name is not None:
            return self._name
        return f"{self.type}_{id(self)}"

    @name.setter
    def name(self, value: str):
        self._name = value

    def _set_parents(self):
        for child in self.children:
            child.parent = self

    def walk(self):
        """Iterate over this shape and all descendants."""
        yield self
        for child in self.children:
            if isinstance(child, Shape):
                yield from child.walk()

    def evaluate_params(self, context: dict[str, Any] | None = None,
                        _visited: set | None = None) -> dict[str, Any]:
        """Evaluate all parameters in this subtree and return the context."""
        if context is None:
            context = {}
        if _visited is None:
            _visited = set()
        shape_id = id(self)
        if shape_id in _visited:
            return context
        _visited.add(shape_id)

        for name, param in self.params.items():
            # Use the Parameter's own name as the context key
            key = param.name if isinstance(param, Parameter) else name
            if key in context:
                continue
            if isinstance(param, Parameter):
                if param.default is not None:
                    if isinstance(param.default, Expression):
                        context[key] = param.default.evaluate(context)
                    else:
                        context[key] = param.default
            elif isinstance(param, Expression):
                context[key] = param.evaluate(context)

        for child in self.children:
            if isinstance(child, Shape):
                child.evaluate_params(context, _visited)
        return context

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a parameter by name, recursing up to parent if needed.

        Searches both dict keys and ``Parameter`` objects by their ``.name``.
        """
        if name in self.params:
            return self.params[name]
        for key, val in self.params.items():
            if isinstance(val, Parameter) and val.name == name:
                return val
        if self.parent is not None:
            return self.parent.get_param(name, default)
        return default

    # ---- operator overloads ----

    def __add__(self, other):
        if isinstance(other, Shape):
            return Union(children=[self, other])
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, Shape):
            return Union(children=[other, self])
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Shape):
            return Difference(positive=self, negatives=[other])
        if isinstance(other, list):
            return Difference(positive=self, negatives=other)
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, Shape):
            return Intersection(children=[self, other])
        return NotImplemented

    def __repr__(self):
        return f"{self.type}({self.name!r})"


# ---------------------------------------------------------------------------
# Shape parameter helpers
# ---------------------------------------------------------------------------

def make_param(name: str, default: Any = None) -> Parameter:
    """Shorthand for creating a Parameter."""
    return Parameter(name, default)


# ---------------------------------------------------------------------------
# Primitives -- 3D
# ---------------------------------------------------------------------------

class Box(Shape):
    """Rectangular cuboid defined by length, width, height."""

    type = "Box"

    def __init__(self, length, width, height, name=None):
        super().__init__(name=name)
        self.params["length"] = _resolve_dim(length)
        self.params["width"] = _resolve_dim(width)
        self.params["height"] = _resolve_dim(height)


class Cylinder(Shape):
    """Cylinder (or truncated cone) defined by height, radius1, radius2.

    If radius2 is omitted or 0, a standard cylinder is produced.
    If radius2 > 0, a truncated cone is produced.
    """

    type = "Cylinder"

    def __init__(self, height, radius, radius2=None, name=None):
        super().__init__(name=name)
        self.params["height"] = _resolve_dim(height)
        self.params["radius"] = _resolve_dim(radius)
        if radius2 is not None:
            self.params["radius2"] = _resolve_dim(radius2)


class Sphere(Shape):
    """Sphere defined by radius."""

    type = "Sphere"

    def __init__(self, radius, name=None):
        super().__init__(name=name)
        self.params["radius"] = _resolve_dim(radius)


class Cone(Shape):
    """Cone defined by height, bottom radius, top radius."""

    type = "Cone"

    def __init__(self, height, radius1, radius2=0, name=None):
        super().__init__(name=name)
        self.params["height"] = _resolve_dim(height)
        self.params["radius1"] = _resolve_dim(radius1)
        self.params["radius2"] = _resolve_dim(radius2)


class Torus(Shape):
    """Torus defined by major radius (center to tube center) and minor radius (tube radius)."""

    type = "Torus"

    def __init__(self, majorRadius, minorRadius, name=None):
        super().__init__(name=name)
        self.params["majorRadius"] = _resolve_dim(majorRadius)
        self.params["minorRadius"] = _resolve_dim(minorRadius)


class Wedge(Shape):
    """Right triangular prism defined by length, width, height."""

    type = "Wedge"

    def __init__(self, length, width, height, name=None):
        super().__init__(name=name)
        self.params["length"] = _resolve_dim(length)
        self.params["width"] = _resolve_dim(width)
        self.params["height"] = _resolve_dim(height)


class Prism(Shape):
    """Generic prism extruded from a 2D polygon."""

    type = "Prism"

    def __init__(self, polygon: list[tuple[float, float]], height, name=None):
        super().__init__(name=name)
        self.params["polygon"] = polygon
        self.params["height"] = _resolve_dim(height)


# ---------------------------------------------------------------------------
# 2D primitives
# ---------------------------------------------------------------------------

class Polygon(Shape):
    """Closed 2D polygon defined by a list of (x, y) points."""

    type = "Polygon"

    def __init__(self, points: list[tuple[float, float]], name=None):
        super().__init__(name=name)
        self.params["points"] = points


class Circle(Shape):
    """2D circle defined by radius."""

    type = "Circle"

    def __init__(self, radius, name=None):
        super().__init__(name=name)
        self.params["radius"] = _resolve_dim(radius)


class Rectangle(Shape):
    """2D rectangle defined by width and height."""

    type = "Rectangle"

    def __init__(self, width, height, name=None):
        super().__init__(name=name)
        self.params["width"] = _resolve_dim(width)
        self.params["height"] = _resolve_dim(height)


class Text(Shape):
    """2D text shape."""

    type = "Text"

    def __init__(self, text: str, size=10, name=None):
        super().__init__(name=name)
        self.params["text"] = text
        self.params["size"] = _resolve_dim(size)


# ---------------------------------------------------------------------------
# 2D -> 3D operations
# ---------------------------------------------------------------------------

class Extrude(Shape):
    """Extrude a 2D shape along the Z axis."""

    type = "Extrude"

    def __init__(self, shape: Shape, height, twist=0, slices=None, name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["height"] = _resolve_dim(height)
        if twist:
            self.params["twist"] = _resolve_dim(twist)
        if slices is not None:
            self.params["slices"] = _resolve_dim(slices)


class Revolve(Shape):
    """Revolve a 2D shape around an axis."""

    type = "Revolve"

    def __init__(self, shape: Shape, angle=360, axis=(0, 0, 1), name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["angle"] = _resolve_dim(angle)
        self.params["axis"] = axis


class Loft(Shape):
    """Loft between multiple 2D shapes."""

    type = "Loft"

    def __init__(self, shapes: list[Shape], name=None):
        super().__init__(name=name)
        self.children = list(shapes)
        self._set_parents()
        self.params["shapes"] = shapes


class Sweep(Shape):
    """Sweep a 2D shape along a path."""

    type = "Sweep"

    def __init__(self, shape: Shape, path: Shape, name=None):
        super().__init__(name=name)
        self.children = [shape, path]
        self._set_parents()
        self.params["shape"] = shape
        self.params["path"] = path


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

class Translate(Shape):
    """Translate a shape by (x, y, z)."""

    type = "Translate"

    def __init__(self, shape: Shape, x=0, y=0, z=0, name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["x"] = _resolve_dim(x)
        self.params["y"] = _resolve_dim(y)
        self.params["z"] = _resolve_dim(z)
        self.params["shape"] = shape


class Rotate(Shape):
    """Rotate a shape by angle degrees around axis (ax, ay, az)."""

    type = "Rotate"

    def __init__(self, shape: Shape, angle=0, axis=(0, 0, 1), name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["angle"] = _resolve_dim(angle)
        self.params["axis"] = axis
        self.params["shape"] = shape


class RotateXYZ(Shape):
    """Rotate a shape by (x, y, z) Euler angles in degrees."""

    type = "RotateXYZ"

    def __init__(self, shape: Shape, x=0, y=0, z=0, name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["x"] = _resolve_dim(x)
        self.params["y"] = _resolve_dim(y)
        self.params["z"] = _resolve_dim(z)
        self.params["shape"] = shape


class Scale(Shape):
    """Scale a shape by a factor (scalar or 3-tuple)."""

    type = "Scale"

    def __init__(self, shape: Shape, factor=(1, 1, 1), name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        if isinstance(factor, (int, float)):
            factor = (factor, factor, factor)
        self.params["factor"] = factor


class Mirror(Shape):
    """Mirror a shape across a plane defined by a normal vector."""

    type = "Mirror"

    def __init__(self, shape: Shape, normal=(1, 0, 0), name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["normal"] = normal


# ---------------------------------------------------------------------------
# CSG Operations
# ---------------------------------------------------------------------------

class Union(Shape):
    """Boolean union of multiple shapes."""

    type = "Union"

    def __init__(self, children=None, name=None):
        super().__init__(name=name)
        flat = []
        for child in (children or []):
            if isinstance(child, Union):
                flat.extend(child.children)
            elif isinstance(child, Shape):
                flat.append(child)
        self.children = flat
        self._set_parents()

    def __add__(self, other):
        if isinstance(other, Shape):
            self.children.append(other)
            other.parent = self
            return self
        return NotImplemented


class Difference(Shape):
    """Boolean difference: subtract one or more shapes from a positive shape."""

    type = "Difference"

    def __init__(self, positive: Shape, negatives: list[Shape] | None = None,
                 name=None):
        super().__init__(name=name)
        self.positive = positive
        self.negatives = negatives or []
        self.children = [positive] + self.negatives
        self._set_parents()

    def __sub__(self, other):
        if isinstance(other, Shape):
            self.negatives.append(other)
            self.children.append(other)
            other.parent = self
            return self
        return NotImplemented


class Intersection(Shape):
    """Boolean intersection of multiple shapes."""

    type = "Intersection"

    def __init__(self, children=None, name=None):
        super().__init__(name=name)
        flat = []
        for child in (children or []):
            if isinstance(child, Intersection):
                flat.extend(child.children)
            elif isinstance(child, Shape):
                flat.append(child)
        self.children = flat
        self._set_parents()

    def __mul__(self, other):
        if isinstance(other, Shape):
            self.children.append(other)
            other.parent = self
            return self
        return NotImplemented


# ---------------------------------------------------------------------------
# Modules (reusable named blocks)
# ---------------------------------------------------------------------------

class Module(Shape):
    """A reusable module definition wrapping an inner shape.

    When rendered, the module is emitted as a separate ``module`` block
    and referenced by name.
    """

    type = "Module"

    def __init__(self, shape: Shape, module_name: str | None = None,
                 export_params: list[str] | None = None, name=None):
        super().__init__(name=name or module_name)
        self.children = [shape]
        self._set_parents()
        self.params["module_name"] = module_name or self._name or "unnamed"
        self.params["export_params"] = export_params or []
        self.params["shape"] = shape


class ModuleRef(Shape):
    """Reference to a previously defined module.

    Arguments match the module's ``export_params`` in order.
    """

    type = "ModuleRef"

    def __init__(self, module_name: str, args: list | None = None, name=None):
        super().__init__(name=name)
        self.params["module_name"] = module_name
        self.params["args"] = args or []


# ---------------------------------------------------------------------------
# Appearance modifiers
# ---------------------------------------------------------------------------

class Color(Shape):
    """Apply a color to a shape.

    Accepts an OpenSCAD color name (``"red"``), hex (``"#FF0000"``),
    or an ``[r, g, b, a]`` list.
    """

    type = "Color"

    def __init__(self, shape: Shape, color: str | list, name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["color"] = color


class Modifier(Shape):
    """CSG modifier that controls how a shape is displayed during preview.

    Modifiers:
        "debug"   -- ``#``  (show all CSG operations, transparent)
        "background" -- ``%`` (transparent / ghosted)
        "only"    -- ``!``  (show only this shape)
        "disable"  -- ``*`` (disable this shape, treat as comment)
    """

    type = "Modifier"

    VALID_MODIFIERS = ("debug", "background", "only", "disable")

    def __init__(self, shape: Shape, modifier: str = "debug", name=None):
        super().__init__(name=name)
        if modifier not in self.VALID_MODIFIERS:
            raise ValueError(f"Unknown modifier: {modifier!r}. "
                             f"Valid: {self.VALID_MODIFIERS}")
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["modifier"] = modifier


# ---------------------------------------------------------------------------
# Hull / Minkowski / Offset
# ---------------------------------------------------------------------------

class Hull(Shape):
    """Convex hull of multiple shapes."""

    type = "Hull"

    def __init__(self, children=None, name=None):
        super().__init__(name=name)
        self.children = list(children) if children else []
        self._set_parents()


class Minkowski(Shape):
    """Minkowski sum of two or more shapes."""

    type = "Minkowski"

    def __init__(self, children=None, name=None):
        super().__init__(name=name)
        self.children = list(children) if children else []
        self._set_parents()


class Offset(Shape):
    """2D offset operation (for inflating / deflating 2D profiles)."""

    type = "Offset"

    def __init__(self, shape: Shape, r=0, chamfer=False, name=None):
        super().__init__(name=name)
        self.children = [shape]
        self._set_parents()
        self.params["shape"] = shape
        self.params["r"] = _resolve_dim(r)
        self.params["chamfer"] = chamfer


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

class Assembly(Shape):
    """Named assembly of shapes with explicit positioning.

    Each child shape carries its own Translate/Rotate for placement.
    """

    type = "Assembly"

    def __init__(self, name=None):
        super().__init__(name=name)

    def place(self, shape: Shape, x=0, y=0, z=0, rotate_angle=0,
              rotate_axis=(0, 0, 1)) -> Shape:
        if x != 0 or y != 0 or z != 0:
            shape = Translate(shape, x, y, z)
        if rotate_angle != 0:
            shape = Rotate(shape, rotate_angle, rotate_axis)
        self.children.append(shape)
        shape.parent = self
        return shape


class Connection:
    """A named connection between two shapes in an assembly.

    Analogous to SysML v2 ``connection`` or OpenSCAD joints.
    """

    def __init__(self, name: str, source: Shape, target: Shape,
                 kind: str = "mate"):
        self.name = name
        self.source = source
        self.target = target
        self.kind = kind  # 'mate', 'align', 'insert', 'screw', etc.

    def __repr__(self):
        return f"Connection({self.name!r}: {self.source.name!r} -> {self.target.name!r})"
