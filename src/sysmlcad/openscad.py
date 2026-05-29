"""OpenSCAD backend -- renders a Shape IR tree to OpenSCAD source code.

Usage:
    from sysmlcad import Box, Cylinder, export
    box = Box(100, 50, 30)
    print(export(box, backend="openscad"))
    # -> cube([100, 50, 30]);

Options passed to ``render()`` / ``export(..., backend="openscad", ...)``:

    fn : int | None
        Set ``$fn`` for curved-surface resolution (default None = not set).
    fa : float | None
        Set ``$fa`` minimum angle (default None).
    fs : float | None
        Set ``$fs`` minimum fragment size (default None).
    preamble : str
        Extra text prepended to the output.
    module_names : bool
        Whether to emit ``module`` wrappers for named top-level shapes.
"""

from __future__ import annotations

import io
from typing import Any

from sysmlcad.backend import ShapeBackend, register_backend
from sysmlcad.ir import (
    Shape,
    Box, Cylinder, Sphere, Cone, Torus, Wedge, Prism,
    Polygon, Circle, Rectangle, Text,
    Extrude, Revolve, Loft, Sweep,
    Translate, Rotate, RotateXYZ, Scale, Mirror,
    Union, Difference, Intersection,
    Module, ModuleRef,
    Color, Modifier,
    Hull, Minkowski, Offset,
    Assembly, Connection,
    Parameter,
)
from sysmlcad.expression import (
    Expression, Literal, ParameterRef, BinaryOp, UnaryOp, FunctionCall,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODIFIER_SYMBOLS = {
    "debug": "#",
    "background": "%",
    "only": "!",
    "disable": "*",
}


def _eval(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, Expression):
        return value.evaluate(context)
    if isinstance(value, Parameter):
        return value.evaluate(context)
    return value


def _val_str(value: Any, context: dict[str, Any]) -> str:
    evaled = _eval(value, context)
    if hasattr(evaled, "units"):
        try:
            return str(evaled.to("mm").magnitude)
        except Exception:
            return str(evaled.magnitude)
    if isinstance(evaled, float):
        s = f"{evaled:.10f}".rstrip("0").rstrip(".")
        return s if s != "" else "0"
    return str(evaled)


def _vec3(x, y, z, context: dict[str, Any]) -> str:
    return f"[{_val_str(x, context)}, {_val_str(y, context)}, {_val_str(z, context)}]"


_f32 = _val_str


def _color_str(color: str | list) -> str:
    if isinstance(color, str):
        return f'"{color}"'
    return str(color)


def _expr_str(value: Any, context: dict[str, Any]) -> str:
    """Render an expression as OpenSCAD code, preserving parameter names.

    Unlike ``_val_str`` which evaluates everything to concrete values,
    this converts the expression tree to OpenSCAD source so that
    ``ParameterRef("L")`` renders as ``L`` and ``(L / 2)`` renders as
    ``(L / 2)``.
    """
    if isinstance(value, Parameter):
        return value.name
    if isinstance(value, ParameterRef):
        return value.name
    if isinstance(value, BinaryOp):
        left = _expr_str(value.left, context)
        right = _expr_str(value.right, context)
        op_symbol = {"add": " + ", "sub": " - ", "mul": " * ",
                     "truediv": " / ", "pow": " ^ "}.get(value.op, f" {value.op} ")
        return f"({left}{op_symbol}{right})"
    if isinstance(value, UnaryOp):
        operand = _expr_str(value.operand, context)
        if value.op == "neg":
            return f"(-{operand})"
        return f"(+{operand})"
    if isinstance(value, FunctionCall):
        args = ", ".join(_expr_str(a, context) for a in value.args)
        return f"{value.name}({args})"
    if isinstance(value, Expression):
        return _val_str(value, context)
    return _val_str(value, context)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class OpenSCADRenderer:
    """Accumulates OpenSCAD source via an indented write."""

    def __init__(self, **options):
        self._buf = io.StringIO()
        self._indent = 0
        self._context: dict[str, Any] = {}
        self._modules: list[tuple[str, str]] = []
        self._module_names: set[str] = set()
        self._options = options
        self._module_mode = False  # when True, use _expr_str instead of _val_str

    # -- value rendering (respects module_mode) --

    def _s(self, value: Any, context: dict[str, Any] | None = None) -> str:
        """Render a value to an OpenSCAD expression string.

        In normal mode, evaluates expressions to concrete values.
        In module mode, preserves parameter names as OpenSCAD variables.
        """
        ctx = context if context is not None else self._context
        if self._module_mode:
            return _expr_str(value, ctx)
        return _val_str(value, ctx)

    def _v3(self, x, y, z) -> str:
        return f"[{self._s(x)}, {self._s(y)}, {self._s(z)}]"

    # -- write helpers --

    def write(self, line: str = ""):
        if line:
            self._buf.write("  " * self._indent + line + "\n")
        else:
            self._buf.write("\n")

    def indent(self):
        self._indent += 1

    def dedent(self):
        self._indent -= 1

    @property
    def source(self) -> str:
        return self._buf.getvalue()

    # -- prelude --

    def _write_prelude(self):
        fn = self._options.get("fn")
        fa = self._options.get("fa")
        fs = self._options.get("fs")
        if fn is not None:
            self.write(f"$fn = {fn};")
        if fa is not None:
            self.write(f"$fa = {fa};")
        if fs is not None:
            self.write(f"$fs = {fs};")
        preamble = self._options.get("preamble")
        if preamble:
            for line in preamble.strip().split("\n"):
                self.write(f"// {line}")

    # -- main entry point --

    def render(self, shape: Shape) -> str:
        self._context = shape.evaluate_params()
        self._collect_modules(shape)
        self._write_prelude()
        self._emit_module_definitions()
        self._write_main_body(shape)
        return self.source

    def _collect_modules(self, shape: Shape):
        for node in shape.walk():
            if isinstance(node, Module):
                self._collect_module_definition(node)
            elif isinstance(node, Shape):
                pass

    def _collect_module_definition(self, node: Module):
        module_name = node.params["module_name"]
        if module_name in self._module_names:
            return
        self._module_names.add(module_name)

        export_params = node.params["export_params"]

        buf = io.StringIO()
        old_buf = self._buf
        old_context = self._context
        old_module_mode = self._module_mode
        self._buf = buf
        self._context = {}
        self._module_mode = True
        old_indent = self._indent
        self._indent = 0

        params_str = ", ".join(export_params) if export_params else ""
        self.write(f"module {module_name}({params_str}) {{")
        self.indent()
        for child in node.children:
            self._render_shape(child)
        self.dedent()
        self.write("}")

        self._indent = old_indent
        content = buf.getvalue()
        self._context = old_context
        self._module_mode = old_module_mode
        self._buf = old_buf
        self._modules.append((module_name, content))

    def _emit_module_definitions(self):
        if not self._modules:
            return
        for name, content in self._modules:
            self._buf.write(content + "\n\n")

    def _write_main_body(self, shape: Shape):
        if isinstance(shape, Module):
            module_name = shape.params["module_name"]
            export_params = shape.params["export_params"]
            args = ", ".join(
                self._s(p, self._context) if isinstance(p, (int, float, str, Expression, Parameter))
                else str(p)
                for p in export_params
            ) if export_params else ""
            self.write(f"{module_name}({args});")
        else:
            self._render_shape(shape)

    # -- dispatch --

    def _render_shape(self, shape: Shape):
        dispatch = {
            Box: self._box,
            Cylinder: self._cylinder,
            Sphere: self._sphere,
            Cone: self._cone,
            Torus: self._torus,
            Wedge: self._wedge,
            Prism: self._prism,
            Polygon: self._polygon,
            Circle: self._circle_2d,
            Rectangle: self._rectangle_2d,
            Text: self._text,
            Extrude: self._extrude,
            Revolve: self._revolve,
            Loft: self._loft,
            Sweep: self._sweep,
            Translate: self._translate,
            Rotate: self._rotate,
            RotateXYZ: self._rotate_xyz,
            Scale: self._scale,
            Mirror: self._mirror,
            Union: self._union,
            Difference: self._difference,
            Intersection: self._intersection,
            Module: self._module_ref,
            ModuleRef: self._module_ref,
            Color: self._color,
            Modifier: self._modifier,
            Hull: self._hull,
            Minkowski: self._minkowski,
            Offset: self._offset,
            Assembly: self._assembly,
        }
        handler = dispatch.get(type(shape))
        if handler is None:
            self.write(f"// WARNING: Unsupported shape type: {type(shape).__name__}")
            return
        handler(shape)

    # ---- primitives ----

    def _box(self, shape: Box):
        c = self._context
        self.write(f"cube([{self._s(shape.params['length'], c)}, "
                    f"{self._s(shape.params['width'], c)}, "
                    f"{self._s(shape.params['height'], c)}]);")

    def _cylinder(self, shape: Cylinder):
        c = self._context
        h = self._s(shape.params["height"], c)
        r1 = self._s(shape.params["radius"], c)
        if "radius2" in shape.params:
            r2 = self._s(shape.params["radius2"], c)
            if r2 != r1:
                self.write(f"cylinder(h={h}, r1={r1}, r2={r2});")
                return
        self.write(f"cylinder(h={h}, r={r1});")

    def _sphere(self, shape: Sphere):
        self.write(f"sphere(r={self._s(shape.params['radius'], self._context)});")

    def _cone(self, shape: Cone):
        c = self._context
        self.write(f"cylinder(h={self._s(shape.params['height'], c)}, "
                    f"r1={self._s(shape.params['radius1'], c)}, "
                    f"r2={self._s(shape.params['radius2'], c)});")

    def _torus(self, shape: Torus):
        c = self._context
        maj = self._s(shape.params["majorRadius"], c)
        min_r = self._s(shape.params["minorRadius"], c)
        self.write(f"// Torus (major={maj}, minor={min_r})")
        self.write(f"rotate_extrude(convexity=10)")
        self.indent()
        self.write(f"translate([{maj}, 0, 0])")
        self.indent()
        self.write(f"circle(r={min_r});")
        self.dedent()
        self.dedent()

    def _wedge(self, shape: Wedge):
        c = self._context
        l = self._s(shape.params["length"], c)
        w = self._s(shape.params["width"], c)
        h = self._s(shape.params["height"], c)
        self.write(f"// Wedge (right triangular prism)")
        self.write(f"linear_extrude(height={h})")
        self.indent()
        self.write(f"polygon(points=[[0,0],[{l},0],[0,{w}]]);")
        self.dedent()

    def _prism(self, shape: Prism):
        c = self._context
        pts = shape.params["polygon"]
        h = self._s(shape.params["height"], c)
        pts_str = ", ".join(f"[{p[0]},{p[1]}]" for p in pts)
        self.write(f"linear_extrude(height={h})")
        self.indent()
        self.write(f"polygon(points=[{pts_str}]);")
        self.dedent()

    # ---- 2D primitives ----

    def _polygon(self, shape: Polygon):
        pts = shape.params["points"]
        pts_str = ", ".join(f"[{p[0]},{p[1]}]" for p in pts)
        self.write(f"polygon(points=[{pts_str}]);")

    def _circle_2d(self, shape: Circle):
        self.write(f"circle(r={self._s(shape.params['radius'], self._context)});")

    def _rectangle_2d(self, shape: Rectangle):
        c = self._context
        self.write(f"square([{self._s(shape.params['width'], c)}, "
                    f"{self._s(shape.params['height'], c)}]);")

    def _text(self, shape: Text):
        txt = shape.params["text"]
        sz = self._s(shape.params["size"], self._context)
        self.write(f'text("{txt}", size={sz});')

    # ---- 2D -> 3D ----

    def _extrude(self, shape: Extrude):
        c = self._context
        h = self._s(shape.params["height"], c)
        twist = self._s(shape.params.get("twist", Literal(0)), c) if "twist" in shape.params else 0
        slices = shape.params.get("slices")
        if slices is not None:
            sl = self._s(slices, c)
            self.write(f"linear_extrude(height={h}, twist={twist}, slices={sl})")
        elif twist:
            self.write(f"linear_extrude(height={h}, twist={twist})")
        else:
            self.write(f"linear_extrude(height={h})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _revolve(self, shape: Revolve):
        c = self._context
        angle = self._s(shape.params["angle"], c)
        self.write(f"rotate_extrude(angle={angle}, convexity=10)"
                    if angle != 360 else "rotate_extrude(convexity=10)")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _loft(self, shape: Loft):
        self.write("// Loft -- no direct OpenSCAD equivalent; using hull chain")
        children = shape.children
        for i, child in enumerate(children):
            self.write(f"// slice {i}")
            self._render_shape(child)
            if i > 0:
                self.write(f"// hull between slice {i-1} and slice {i}")

    def _sweep(self, shape: Sweep):
        self.write("// Sweep -- no direct OpenSCAD equivalent")

    # ---- transforms ----

    def _translate(self, shape: Translate):
        self.write(f"translate({self._v3(shape.params['x'], shape.params['y'], shape.params['z'])})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _rotate(self, shape: Rotate):
        c = self._context
        angle = self._s(shape.params["angle"], c)
        axis = shape.params["axis"]
        self.write(f"rotate(a={angle}, v={axis})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _rotate_xyz(self, shape: RotateXYZ):
        self.write(f"rotate({self._v3(shape.params['x'], shape.params['y'], shape.params['z'])})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _scale(self, shape: Scale):
        self.write(f"scale({shape.params['factor']})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _mirror(self, shape: Mirror):
        self.write(f"mirror({shape.params['normal']})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    # ---- CSG ----

    def _union(self, shape: Union):
        if not shape.children:
            return
        self.write("union()")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _difference(self, shape: Difference):
        self.write("difference()")
        self.indent()
        self._render_shape(shape.positive)
        for neg in shape.negatives:
            self._render_shape(neg)
        self.dedent()

    def _intersection(self, shape: Intersection):
        if not shape.children:
            return
        self.write("intersection()")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    # ---- modules ----

    def _module_ref(self, shape: Module | ModuleRef):
        """Render a module usage or reference."""
        if isinstance(shape, Module):
            module_name = shape.params["module_name"]
            args = shape.params["export_params"]
            args_str = ", ".join(
                self._s(a if isinstance(a, (int, float, Expression, Parameter)) else a, self._context)
                for a in args
            ) if args else ""
        else:
            module_name = shape.params["module_name"]
            raw_args = shape.params["args"]
            args_str = ", ".join(
                self._s(a, self._context) if isinstance(a, (int, float, Expression, Parameter))
                else str(a)
                for a in raw_args
            ) if raw_args else ""
        self.write(f"{module_name}({args_str});")

    # ---- appearance ----

    def _color(self, shape: Color):
        color = shape.params["color"]
        self.write(f"color({_color_str(color)})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _modifier(self, shape: Modifier):
        modifier = shape.params["modifier"]
        symbol = _MODIFIER_SYMBOLS[modifier]
        for child in shape.children:
            self._render_shape(child)
        lines = self.source.rstrip().split("\n")
        if lines:
            last_line = lines[-1]
            self._buf = io.StringIO()
            self._buf.write("\n".join(lines[:-1]))
            if lines[:-1]:
                self._buf.write("\n")
            # Prepend modifier character to the last emitted line
            self._buf.write(f"{symbol} {last_line.lstrip()}\n")

    def _hull(self, shape: Hull):
        if not shape.children:
            return
        self.write("hull()")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _minkowski(self, shape: Minkowski):
        if not shape.children:
            return
        self.write("minkowski()")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    def _offset(self, shape: Offset):
        c = self._context
        r = self._s(shape.params["r"], c)
        chamfer = shape.params["chamfer"]
        if chamfer:
            self.write(f"offset(r={r}, chamfer=true)")
        else:
            self.write(f"offset(r={r})")
        self.indent()
        for child in shape.children:
            self._render_shape(child)
        self.dedent()

    # ---- assembly ----

    def _assembly(self, shape: Assembly):
        if shape.children:
            self.write("union()")
            self.indent()
            for child in shape.children:
                self._render_shape(child)
            self.dedent()


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

@register_backend
class OpenSCADBackend(ShapeBackend):
    """Render Shape IR to OpenSCAD source code.

    Extra ``**options`` passed to ``render()``:

    * ``fn`` -- set ``$fn`` for curved surfaces
    * ``fa`` -- set ``$fa`` minimum angle
    * ``fs`` -- set ``$fs`` minimum fragment size
    * ``preamble`` -- extra comment text at top of output
    """

    def render(self, shape: Shape, **options) -> str:
        renderer = OpenSCADRenderer(**options)
        return renderer.render(shape)

    def mime_type(self) -> str:
        return "text/x-openscad"

    def file_extension(self) -> str:
        return ".scad"
