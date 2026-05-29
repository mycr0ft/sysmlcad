"""Build123d backend — renders a Shape IR tree to Build123d Python source code.

Usage:
    from sysmlcad import Box, Cylinder, export
    box = Box(100, 50, 30)
    print(export(box, backend="build123d"))
    # → _s1 = Box(100.0, 50.0, 30.0)
    #   result = _s1

The generated code imports build123d and uses its native API.
Run the output with ``python`` (requires ``build123d`` installed).
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
# Helpers (shared with openscad backend)
# ---------------------------------------------------------------------------

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


def _expr_str(value: Any, context: dict[str, Any]) -> str:
    """Render an expression as Python code, preserving parameter names."""
    if isinstance(value, Parameter):
        return value.name
    if isinstance(value, ParameterRef):
        return value.name
    if isinstance(value, BinaryOp):
        left = _expr_str(value.left, context)
        right = _expr_str(value.right, context)
        op_symbol = {"add": " + ", "sub": " - ", "mul": " * ",
                     "truediv": " / ", "pow": " ** "}.get(value.op, f" {value.op} ")
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


def _color_str(color: str | list) -> str:
    if isinstance(color, str):
        return f'"{color}"'
    return str(color)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Build123dRenderer:
    """Accumulates Build123d Python source via an indented write."""

    def __init__(self, **options):
        self._buf = io.StringIO()
        self._indent = 0
        self._context: dict[str, Any] = {}
        self._modules: list[tuple[str, str]] = []
        self._module_names: set[str] = set()
        self._var_counter = 0
        self._options = options
        self._module_mode = False

    # -- variable naming --

    def _next_var(self, prefix="s") -> str:
        self._var_counter += 1
        return f"_{prefix}_{self._var_counter}"

    # -- value rendering (respects module_mode) --

    def _s(self, value: Any, context: dict[str, Any] | None = None) -> str:
        ctx = context if context is not None else self._context
        if self._module_mode:
            return _expr_str(value, ctx)
        return _val_str(value, ctx)

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

    # -- preamble --

    def _write_preamble(self):
        self.write("from build123d import *")
        preamble = self._options.get("preamble")
        if preamble:
            for line in preamble.strip().split("\n"):
                self.write(f"# {line}")

    # -- main entry point --

    def render(self, shape: Shape) -> str:
        self._context = shape.evaluate_params()
        self._collect_modules(shape)
        self._write_preamble()
        self._emit_module_definitions()
        result_var = self._write_main_body(shape)
        self.write(f"result = {result_var}")
        return self.source

    def _collect_modules(self, shape: Shape):
        for node in shape.walk():
            if isinstance(node, Module):
                self._collect_module_definition(node)

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
        old_var_counter = self._var_counter
        self._buf = buf
        self._context = {}
        self._module_mode = True
        self._var_counter = 0

        params_str = ", ".join(export_params) if export_params else ""
        self.write(f"def {module_name}({params_str}):")
        self.indent()
        last_var = None
        for child in node.children:
            last_var = self._render_shape(child)
        if last_var is not None:
            self.write(f"return {last_var}")
        self.dedent()

        self._var_counter = old_var_counter
        content = buf.getvalue()
        self._context = old_context
        self._module_mode = old_module_mode
        self._buf = old_buf
        self._modules.append((module_name, content))

    def _emit_module_definitions(self):
        if not self._modules:
            return
        for name, content in self._modules:
            self._buf.write(content + "\n")

    def _write_main_body(self, shape: Shape) -> str | None:
        if isinstance(shape, Module):
            module_name = shape.params["module_name"]
            export_params = shape.params["export_params"]
            args = ", ".join(
                self._s(p, self._context) if isinstance(p, (int, float, str, Expression, Parameter))
                else str(p)
                for p in export_params
            ) if export_params else ""
            var = self._next_var("call")
            self.write(f"{var} = {module_name}({args})")
            return var
        return self._render_shape(shape)

    # -- dispatch --

    def _render_shape(self, shape: Shape) -> str | None:
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
            var = self._next_var("unknown")
            self.write(f"# {var}: unsupported {type(shape).__name__}")
            return var
        return handler(shape)

    # ---- primitives ----

    def _box(self, shape: Box) -> str:
        var = self._next_var("box")
        c = self._context
        self.write(f"{var} = Box({self._s(shape.params['length'], c)}, "
                    f"{self._s(shape.params['width'], c)}, "
                    f"{self._s(shape.params['height'], c)})")
        return var

    def _cylinder(self, shape: Cylinder) -> str:
        var = self._next_var("cyl")
        c = self._context
        h = self._s(shape.params["height"], c)
        r = self._s(shape.params["radius"], c)
        self.write(f"{var} = Cylinder(radius={r}, height={h})")
        return var

    def _sphere(self, shape: Sphere) -> str:
        var = self._next_var("sph")
        r = self._s(shape.params["radius"], self._context)
        self.write(f"{var} = Sphere(radius={r})")
        return var

    def _cone(self, shape: Cone) -> str:
        var = self._next_var("cone")
        c = self._context
        h = self._s(shape.params["height"], c)
        r1 = self._s(shape.params["radius1"], c)
        r2 = self._s(shape.params["radius2"], c)
        self.write(f"{var} = Cone(bottom_radius={r1}, top_radius={r2}, height={h})")
        return var

    def _torus(self, shape: Torus) -> str:
        var = self._next_var("tor")
        c = self._context
        maj = self._s(shape.params["majorRadius"], c)
        min_r = self._s(shape.params["minorRadius"], c)
        self.write(f"{var} = Torus(major_radius={maj}, minor_radius={min_r})")
        return var

    def _wedge(self, shape: Wedge) -> str:
        var = self._next_var("wdg")
        c = self._context
        l = self._s(shape.params["length"], c)
        w = self._s(shape.params["width"], c)
        h = self._s(shape.params["height"], c)
        self.write(f"{var} = Box({l}, {w}, {h})  # Wedge — approximated")
        return var

    def _prism(self, shape: Prism) -> str:
        var = self._next_var("prism")
        h = self._s(shape.params["height"], self._context)
        pts = shape.params["polygon"]
        pts_str = ", ".join(f"({p[0]},{p[1]})" for p in pts)
        # Build123d: extrude a 2D polygon
        self.write(f"_{var}_poly = Polygon([{pts_str}])")
        self.write(f"{var} = extrude(_{var}_poly, amount={h})")
        return var

    # ---- 2D primitives ----

    def _polygon(self, shape: Polygon) -> str:
        var = self._next_var("poly")
        pts = shape.params["points"]
        pts_str = ", ".join(f"({p[0]},{p[1]})" for p in pts)
        self.write(f"{var} = Polygon([{pts_str}])")
        return var

    def _circle_2d(self, shape: Circle) -> str:
        var = self._next_var("circ")
        r = self._s(shape.params["radius"], self._context)
        self.write(f"{var} = Circle(radius={r})")
        return var

    def _rectangle_2d(self, shape: Rectangle) -> str:
        var = self._next_var("rect")
        c = self._context
        w = self._s(shape.params["width"], c)
        h = self._s(shape.params["height"], c)
        self.write(f"{var} = Rectangle({w}, {h})")
        return var

    def _text(self, shape: Text) -> str:
        var = self._next_var("txt")
        txt = shape.params["text"]
        sz = self._s(shape.params["size"], self._context)
        self.write(f"{var} = Text({txt!r}, font_size={sz})")
        return var

    # ---- 2D -> 3D ----

    def _extrude(self, shape: Extrude) -> str:
        var = self._next_var("extr")
        c = self._context
        h = self._s(shape.params["height"], c)
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = extrude({child_var}, amount={h})")
        return var

    def _revolve(self, shape: Revolve) -> str:
        var = self._next_var("rev")
        c = self._context
        angle = self._s(shape.params["angle"], c)
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = revolve({child_var}, angle={angle})")
        return var

    def _loft(self, shape: Loft) -> str:
        var = self._next_var("loft")
        child_vars = [self._render_shape(c) for c in shape.children]
        self.write(f"{var} = loft([{', '.join(child_vars)}])")
        return var

    def _sweep(self, shape: Sweep) -> str:
        var = self._next_var("swp")
        path_var = self._render_shape(shape.children[1])
        profile_var = self._render_shape(shape.children[0])
        self.write(f"{var} = sweep({profile_var}, path={path_var})")
        return var

    # ---- transforms ----

    def _translate(self, shape: Translate) -> str:
        var = self._next_var("tr")
        c = self._context
        x = self._s(shape.params["x"], c)
        y = self._s(shape.params["y"], c)
        z = self._s(shape.params["z"], c)
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var} * Pos({x}, {y}, {z})")
        return var

    def _rotate(self, shape: Rotate) -> str:
        var = self._next_var("rot")
        c = self._context
        angle = self._s(shape.params["angle"], c)
        axis = shape.params["axis"]
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var} * Rot({axis}, {angle})")
        return var

    def _rotate_xyz(self, shape: RotateXYZ) -> str:
        var = self._next_var("rotxyz")
        c = self._context
        x = self._s(shape.params["x"], c)
        y = self._s(shape.params["y"], c)
        z = self._s(shape.params["z"], c)
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var}")
        if x != 0:
            self.write(f"{var} = {var} * Rot(1.0, 0.0, 0.0, {x})")
        if y != 0:
            self.write(f"{var} = {var} * Rot(0.0, 1.0, 0.0, {y})")
        if z != 0:
            self.write(f"{var} = {var} * Rot(0.0, 0.0, 1.0, {z})")
        return var

    def _scale(self, shape: Scale) -> str:
        var = self._next_var("sc")
        factor = shape.params["factor"]
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var} * Scale({factor})")
        return var

    def _mirror(self, shape: Mirror) -> str:
        var = self._next_var("mir")
        normal = shape.params["normal"]
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var} * Mirror({normal})")
        return var

    # ---- CSG ----

    def _union(self, shape: Union) -> str | None:
        if not shape.children:
            return None
        var = self._next_var("union")
        child_vars = [self._render_shape(c) for c in shape.children]
        expr = f" + ".join(child_vars)
        self.write(f"{var} = {expr}")
        return var

    def _difference(self, shape: Difference) -> str:
        pos_var = self._render_shape(shape.positive)
        neg_vars = [self._render_shape(neg) for neg in shape.negatives]
        var = self._next_var("diff")
        expr = pos_var
        for nv in neg_vars:
            expr = f"{expr} - {nv}"
        self.write(f"{var} = {expr}")
        return var

    def _intersection(self, shape: Intersection) -> str | None:
        if not shape.children:
            return None
        var = self._next_var("inter")
        child_vars = [self._render_shape(c) for c in shape.children]
        expr = f" * ".join(child_vars)
        self.write(f"{var} = {expr}")
        return var

    # ---- modules ----

    def _module_ref(self, shape: Module | ModuleRef) -> str:
        var = self._next_var("mod")
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
        self.write(f"{var} = {module_name}({args_str})")
        return var

    # ---- appearance ----

    def _color(self, shape: Color) -> str:
        var = self._next_var("col")
        color = shape.params["color"]
        child_var = self._render_shape(shape.children[0])
        self.write(f"{var} = {child_var}  # Build123d: color({_color_str(color)})")
        return var

    def _modifier(self, shape: Modifier) -> str:
        return self._render_shape(shape.children[0])

    # ---- hull / minkowski / offset ----

    def _hull(self, shape: Hull) -> str | None:
        if not shape.children:
            return None
        var = self._next_var("hull")
        child_vars = [self._render_shape(c) for c in shape.children]
        self.write(f"{var} = hull([{', '.join(child_vars)}])")
        return var

    def _minkowski(self, shape: Minkowski) -> str | None:
        if not shape.children:
            return None
        var = self._next_var("mink")
        child_vars = [self._render_shape(c) for c in shape.children]
        self.write(f"{var} = minkowski_sum([{', '.join(child_vars)}])")
        return var

    def _offset(self, shape: Offset) -> str:
        var = self._next_var("off")
        c = self._context
        r = self._s(shape.params["r"], c)
        chamfer = shape.params["chamfer"]
        child_var = self._render_shape(shape.children[0])
        kind = "chamfer" if chamfer else "round"
        self.write(f"{var} = offset({child_var}, amount={r}, kind={kind!r})")
        return var

    # ---- assembly ----

    def _assembly(self, shape: Assembly) -> str:
        if not shape.children:
            return None
        var = self._next_var("assy")
        child_vars = [self._render_shape(c) for c in shape.children]
        expr = f" + ".join(child_vars)
        self.write(f"{var} = {expr}")
        return var


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

@register_backend
class Build123dBackend(ShapeBackend):
    """Render Shape IR to Build123d Python source code.

    Extra ``**options`` passed to ``render()``:

    * ``preamble`` — extra comment text at top of output
    """

    def render(self, shape: Shape, **options) -> str:
        renderer = Build123dRenderer(**options)
        return renderer.render(shape)

    def mime_type(self) -> str:
        return "text/x-python"

    def file_extension(self) -> str:
        return ".py"

    @staticmethod
    def is_available() -> bool:
        try:
            import build123d  # noqa: F401
            return True
        except ImportError:
            return False
