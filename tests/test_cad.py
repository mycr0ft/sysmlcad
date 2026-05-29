"""Tests for the sysmlcad package.

Tests assume no optional CAD dependencies (CadQuery, Build123d, OCP) are
installed.  Only the IR and OpenSCAD backend are tested here.
"""

from __future__ import annotations

import pytest
import pint

from sysmlcad import (
    # IR
    Shape, Box, Cylinder, Sphere, Cone, Torus, Wedge, Prism,
    Polygon, Circle, Rectangle, Text,
    Extrude, Revolve, Union, Difference, Intersection,
    Module, ModuleRef,
    Color, Modifier,
    Hull, Minkowski, Offset,
    Translate, Rotate, RotateXYZ, Scale, Mirror,
    Assembly, Connection,
    # Parameter system
    Parameter, make_param,
    # Expressions
    Expression, Literal, ParameterRef, BinaryOp, UnaryOp, FunctionCall,
    # Backend
    get_backend, list_backends, export,
)


# ===================================================================
# Expression tests
# ===================================================================

class TestExpressions:
    def test_literal_evaluate(self):
        assert Literal(42).evaluate({}) == 42
        assert Literal(3.14).evaluate({}) == 3.14
        assert Literal("hello").evaluate({}) == "hello"

    def test_parameter_ref(self):
        ref = ParameterRef("x")
        assert ref.evaluate({"x": 10}) == 10
        with pytest.raises(ValueError, match="not found"):
            ref.evaluate({})

    def test_binary_op_add(self):
        expr = Literal(5) + Literal(3)
        assert expr.evaluate({}) == 8

    def test_binary_op_sub(self):
        expr = Literal(10) - Literal(3)
        assert expr.evaluate({}) == 7

    def test_binary_op_mul(self):
        expr = Literal(4) * Literal(3)
        assert expr.evaluate({}) == 12

    def test_binary_op_truediv(self):
        expr = Literal(10) / Literal(3)
        assert expr.evaluate({}) == 10 / 3

    def test_binary_op_pow(self):
        expr = Literal(2) ** Literal(10)
        assert expr.evaluate({}) == 1024

    def test_unary_neg(self):
        expr = -Literal(5)
        assert expr.evaluate({}) == -5

    def test_mixed_expression(self):
        x = ParameterRef("x")
        expr = (x + Literal(2)) * Literal(3)
        assert expr.evaluate({"x": 5}) == 21

    def test_function_call_sin(self):
        expr = FunctionCall("sin", Literal(0))
        assert abs(expr.evaluate({})) < 1e-10

    def test_function_call_sqrt(self):
        expr = FunctionCall("sqrt", Literal(16))
        assert expr.evaluate({}) == 4.0

    def test_parameter_class(self):
        p = Parameter("len", 100)
        # Parameter used in expression
        expr = p * 2
        assert isinstance(expr, BinaryOp)
        assert expr.evaluate({"len": 100}) == 200
        # Direct evaluate with context
        assert p.evaluate({"len": 50}) == 50
        # Direct evaluate without context -- uses default
        assert p.evaluate() == 100

    def test_parameter_expression_chain(self):
        length = Parameter("length", 100)
        width = length * 2
        area = length * width
        assert area.evaluate({"length": 100}) == 20000

    def test_expression_equality(self):
        a1 = BinaryOp(Literal(3), Literal(4), "add")
        a2 = BinaryOp(Literal(3), Literal(4), "add")
        b = BinaryOp(Literal(3), Literal(4), "mul")
        assert a1 == a2
        assert a1 != b

    def test_radd_rop(self):
        """Right-hand side operations (e.g., 5 + param)."""
        p = Parameter("x", 10)
        expr = 5 + p
        assert expr.evaluate({"x": 10}) == 15
        expr2 = 5 * p
        assert expr2.evaluate({"x": 10}) == 50


# ===================================================================
# Shape IR tests
# ===================================================================

class TestShapeIR:
    def test_box_creation(self):
        box = Box(10, 20, 30, name="test_box")
        assert box.name == "test_box"
        assert box.type == "Box"
        assert len(box.children) == 0

    def test_box_params(self):
        box = Box(10, 20, 30)
        ctx = box.evaluate_params()
        assert ctx["length"] == 10
        assert ctx["width"] == 20
        assert ctx["height"] == 30

    def test_cylinder_creation(self):
        cyl = Cylinder(40, 5)
        ctx = cyl.evaluate_params()
        assert ctx["height"] == 40
        assert ctx["radius"] == 5

    def test_cylinder_tapered(self):
        cyl = Cylinder(40, 10, radius2=5)
        ctx = cyl.evaluate_params()
        assert ctx["radius2"] == 5

    def test_sphere(self):
        sphere = Sphere(10)
        ctx = sphere.evaluate_params()
        assert ctx["radius"] == 10

    def test_cone(self):
        cone = Cone(20, 10, 3)
        ctx = cone.evaluate_params()
        assert ctx["height"] == 20
        assert ctx["radius1"] == 10
        assert ctx["radius2"] == 3

    def test_torus(self):
        torus = Torus(50, 10)
        ctx = torus.evaluate_params()
        assert ctx["majorRadius"] == 50
        assert ctx["minorRadius"] == 10

    def test_wedge(self):
        wedge = Wedge(30, 20, 10)
        ctx = wedge.evaluate_params()
        assert ctx["length"] == 30
        assert ctx["width"] == 20
        assert ctx["height"] == 10

    def test_walk_single(self):
        box = Box(10, 10, 10)
        walked = list(box.walk())
        assert len(walked) == 1
        assert walked[0] is box

    def test_walk_tree(self):
        box = Box(10, 10, 10)
        cyl = Cylinder(10, 5)
        diff = Difference(box, [cyl])
        walked = list(diff.walk())
        assert len(walked) == 3
        assert walked[0] is diff

    def test_parent_chain(self):
        box = Box(10, 10, 10)
        trans = Translate(box, x=5)
        assert box.parent is trans
        assert trans.parent is None


class TestShapeWithPint:
    def test_box_with_units(self):
        ureg = pint.UnitRegistry()
        box = Box(100 * ureg.mm, 50 * ureg.mm, 30 * ureg.mm)
        ctx = box.evaluate_params()
        assert ctx["length"] == 100 * ureg.mm
        assert ctx["width"] == 50 * ureg.mm
        assert ctx["height"] == 30 * ureg.mm

    def test_unit_conversion(self):
        ureg = pint.UnitRegistry()
        box = Box(1 * ureg.m, 50 * ureg.cm, 300 * ureg.mm)
        ctx = box.evaluate_params()
        # Original quantities preserved
        assert ctx["length"] == 1 * ureg.m
        assert ctx["width"] == 50 * ureg.cm


class TestShapeParameters:
    def test_parameter_in_box(self):
        length = Parameter("length", 100)
        box = Box(length, 50, 30)
        ctx = box.evaluate_params()
        assert ctx["length"] == 100

    def test_parameter_expression_in_box(self):
        length = Parameter("L", 100)
        width = length / 2
        box = Box(length, width, 30)
        ctx = box.evaluate_params()
        assert ctx["L"] == 100
        assert ctx["width"] == 50  # width = L/2 evaluated

    def test_parameter_reference_across_shapes(self):
        height = Parameter("h", 50)
        box1 = Box(10, 20, height)
        box2 = Box(30, 40, height)
        ctx = {}
        ctx = box1.evaluate_params(ctx)
        ctx = box2.evaluate_params(ctx)
        assert ctx["h"] == 50

    def test_get_param_chain(self):
        h = Parameter("h", 50)
        box = Box(10, 20, h)
        trans = Translate(box, z=5)
        # get_param goes UP (child->parent), so box can find "h" on itself
        assert box.get_param("h") is h
        # trans doesn't have "h", and its parent is None
        assert trans.get_param("h") is None


class TestCSGOperations:
    def test_union(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        union = Union([a, b])
        assert len(union.children) == 2

    def test_union_operator(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        union = a + b
        assert isinstance(union, Union)
        assert len(union.children) == 2

    def test_union_chaining(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        c = Sphere(5)
        union = a + b + c
        assert isinstance(union, Union)
        # Chaining: (a + b) -> Union([a,b]); then Union([a,b]) + c -> flat Union([a,b,c])
        assert len(union.children) == 3

    def test_difference(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        diff = Difference(a, [b])
        assert diff.positive is a
        assert len(diff.negatives) == 1

    def test_difference_operator(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        diff = a - b
        assert isinstance(diff, Difference)
        assert diff.positive is a

    def test_intersection(self):
        a = Box(10, 10, 10)
        b = Sphere(10)
        inter = a * b
        assert isinstance(inter, Intersection)


class TestTransforms:
    def test_translate(self):
        box = Box(10, 10, 10)
        t = Translate(box, x=5, y=10, z=15)
        assert t.children[0] is box

    def test_rotate(self):
        cyl = Cylinder(20, 5)
        r = Rotate(cyl, angle=90, axis=(1, 0, 0))
        assert len(r.children) == 1

    def test_rotate_xyz(self):
        box = Box(10, 10, 10)
        r = RotateXYZ(box, x=45, y=30)
        assert len(r.children) == 1

    def test_scale(self):
        sphere = Sphere(5)
        s = Scale(sphere, factor=2)
        assert s.params["factor"] == (2, 2, 2)

    def test_mirror(self):
        box = Box(10, 10, 10)
        m = Mirror(box, normal=(0, 1, 0))
        assert m.params["normal"] == (0, 1, 0)


class Test2Dto3D:
    def test_extrude(self):
        circle = Circle(5)
        ext = Extrude(circle, height=20)
        assert len(ext.children) == 1

    def test_revolve(self):
        rect = Rectangle(10, 5)
        rev = Revolve(rect, angle=180)
        assert len(rev.children) == 1


# ===================================================================
# OpenSCAD Backend tests
# ===================================================================

class TestOpenSCADBackend:
    def test_backend_registered(self):
        names = list_backends()
        assert "openscad" in names

    def test_get_backend(self):
        cls = get_backend("openscad")
        from sysmlcad.openscad import OpenSCADBackend
        assert cls is OpenSCADBackend

    def test_mime_type(self):
        backend = get_backend("openscad")()
        assert backend.mime_type() == "text/x-openscad"

    def test_file_extension(self):
        backend = get_backend("openscad")()
        assert backend.file_extension() == ".scad"

    def test_export_box(self):
        box = Box(100, 50, 30)
        code = export(box, backend="openscad")
        assert "cube([100, 50, 30]);" in code

    def test_export_cylinder(self):
        cyl = Cylinder(40, 5)
        code = export(cyl, backend="openscad")
        assert "cylinder(h=40, r=5);" in code

    def test_export_tapered_cylinder(self):
        cyl = Cylinder(40, 10, radius2=5)
        code = export(cyl, backend="openscad")
        assert "r1=10" in code
        assert "r2=5" in code

    def test_export_sphere(self):
        sphere = Sphere(25)
        code = export(sphere, backend="openscad")
        assert "sphere(r=25);" in code

    def test_export_cone(self):
        cone = Cone(20, 10, 3)
        code = export(cone, backend="openscad")
        assert "r1=10" in code
        assert "r2=3" in code

    def test_export_union(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        union = a + b
        code = export(union, backend="openscad")
        assert "union()" in code
        assert "cube([10, 10, 10])" in code
        assert "cylinder(h=10, r=5)" in code

    def test_export_difference(self):
        box = Box(100, 50, 30)
        hole = Cylinder(30, 5)
        part = box - hole
        code = export(part, backend="openscad")
        assert "difference()" in code
        assert "cube([100, 50, 30])" in code
        assert "cylinder(h=30, r=5)" in code

    def test_export_translate(self):
        box = Box(10, 10, 10)
        t = Translate(box, x=5, y=10, z=15)
        code = export(t, backend="openscad")
        assert "translate([5, 10, 15])" in code
        assert "cube([10, 10, 10])" in code

    def test_export_rotate(self):
        cyl = Cylinder(20, 5)
        r = Rotate(cyl, angle=90, axis=(1, 0, 0))
        code = export(r, backend="openscad")
        assert "rotate(a=90, v=(1, 0, 0))" in code

    def test_export_with_parameter(self):
        length = Parameter("L", 100)
        box = Box(length, 50, 30)
        code = export(box, backend="openscad")
        assert "cube([100, 50, 30]);" in code

    def test_export_with_parameter_expression(self):
        length = Parameter("L", 100)
        width = length / 2
        box = Box(length, width, 30)
        code = export(box, backend="openscad")
        assert "cube([100, 50, 30]);" in code

    def test_export_assembly(self):
        assembly = Assembly(name="bracket")
        bracket = Box(100, 50, 30)
        assembly.place(bracket)
        code = export(assembly, backend="openscad")
        assert "union()" in code
        assert "cube([100, 50, 30])" in code

    def test_export_wedge(self):
        wedge = Wedge(30, 20, 10)
        code = export(wedge, backend="openscad")
        assert "polygon(points=[[0,0],[30,0],[0,20]])" in code

    def test_export_torus(self):
        torus = Torus(50, 10)
        code = export(torus, backend="openscad")
        assert "rotate_extrude" in code

    def test_export_polygon_2d(self):
        poly = Polygon([(0, 0), (10, 0), (5, 10)])
        code = export(poly, backend="openscad")
        assert "[0,0]" in code and "[10,0]" in code and "[5,10]" in code

    def test_export_extrude(self):
        circle = Circle(5)
        ext = Extrude(circle, height=20)
        code = export(ext, backend="openscad")
        assert "linear_extrude(height=20)" in code
        assert "circle(r=5)" in code

    def test_export_with_units_mm(self):
        ureg = pint.UnitRegistry()
        box = Box(100 * ureg.mm, 50 * ureg.mm, 30 * ureg.mm)
        code = export(box, backend="openscad")
        assert "cube([100, 50, 30]);" in code

    def test_export_with_units_m_to_mm(self):
        ureg = pint.UnitRegistry()
        box = Box(1 * ureg.m, 0.5 * ureg.m, 0.3 * ureg.m)
        code = export(box, backend="openscad")
        # Should convert to mm
        assert "cube([1000" in code

    def test_export_scale(self):
        sphere = Sphere(5)
        s = Scale(sphere, factor=2)
        code = export(s, backend="openscad")
        assert "scale((2, 2, 2))" in code

    def test_export_mirror(self):
        box = Box(10, 10, 10)
        m = Mirror(box, normal=(0, 1, 0))
        code = export(m, backend="openscad")
        assert "mirror((0, 1, 0))" in code


# ===================================================================
# Phase 2 -- OpenSCAD backend polish
# ===================================================================

class TestPhase2_Modules:
    def test_module_definition(self):
        shape = Box(100, 50, 30, name="base")
        mod = Module(shape, module_name="base_plate")
        code = export(mod, backend="openscad")
        assert "module base_plate()" in code
        assert "cube([100, 50, 30])" in code

    def test_module_ref(self):
        ref = ModuleRef("base_plate", args=[100, 50, 30])
        code = export(ref, backend="openscad")
        assert "base_plate(100, 50, 30);" in code

    def test_module_with_params(self):
        shape = Box(Parameter("L", 100), Parameter("W", 50), Parameter("H", 30))
        mod = Module(shape, module_name="box_module",
                     export_params=["L", "W", "H"])
        code = export(mod, backend="openscad")
        assert "module box_module(L, W, H)" in code
        assert "cube([L, W, H])" in code


class TestPhase2_Color:
    def test_color_by_name(self):
        sphere = Sphere(10)
        colored = Color(sphere, "red")
        code = export(colored, backend="openscad")
        assert 'color("red")' in code
        assert "sphere(r=10)" in code

    def test_color_rgba(self):
        box = Box(10, 10, 10)
        colored = Color(box, [1, 0, 0, 0.5])
        code = export(colored, backend="openscad")
        assert "color([1, 0, 0, 0.5])" in code


class TestPhase2_Modifier:
    def test_modifier_debug(self):
        box = Box(10, 10, 10)
        mod = Modifier(box, "debug")
        code = export(mod, backend="openscad")
        assert "#" in code

    def test_modifier_background(self):
        box = Box(10, 10, 10)
        mod = Modifier(box, "background")
        code = export(mod, backend="openscad")
        assert "%" in code

    def test_modifier_only(self):
        box = Box(10, 10, 10)
        mod = Modifier(box, "only")
        code = export(mod, backend="openscad")
        assert "!" in code


class TestPhase2_HullMinkowski:
    def test_hull(self):
        a = Sphere(5)
        b = Sphere(10)
        hull = Hull([a, b])
        code = export(hull, backend="openscad")
        assert "hull()" in code
        assert "sphere(r=5)" in code
        assert "sphere(r=10)" in code

    def test_minkowski(self):
        a = Box(10, 10, 10)
        b = Sphere(2)
        mink = Minkowski([a, b])
        code = export(mink, backend="openscad")
        assert "minkowski()" in code
        assert "cube([10, 10, 10])" in code
        assert "sphere(r=2)" in code

    def test_offset(self):
        c = Circle(5)
        off = Offset(c, r=2)
        code = export(off, backend="openscad")
        assert "offset(r=2)" in code
        assert "circle(r=5)" in code

    def test_offset_chamfer(self):
        rect = Rectangle(10, 20)
        off = Offset(rect, r=1, chamfer=True)
        code = export(off, backend="openscad")
        assert "chamfer=true" in code


class TestPhase2_FnOption:
    def test_fn_option(self):
        sphere = Sphere(10)
        code = export(sphere, backend="openscad", fn=64)
        assert "$fn = 64;" in code
        # after $fn line
        idx = code.index("$fn")
        assert idx >= 0

    def test_fa_fs_options(self):
        cyl = Cylinder(10, 5)
        code = export(cyl, backend="openscad", fa=2, fs=0.5)
        assert "$fa = 2;" in code
        assert "$fs = 0.5;" in code

    def test_preamble(self):
        box = Box(10, 10, 10)
        code = export(box, backend="openscad", preamble="Generated by sysmlcad")
        assert "// Generated by sysmlcad" in code


class TestPhase2_ComplexShape:
    def test_bracket_with_all_features(self):
        """Bracket with module, color, modifier, $fn."""
        length = Parameter("L", 100)
        width = Parameter("W", 50)
        height = Parameter("H", 30)

        base = Box(length, width, height, name="base")
        hole = Cylinder(height, Parameter("R", 5))
        part = base - Translate(hole, x=length / 2, y=width / 2)

        mod = Module(part, module_name="bracket",
                     export_params=["L", "W", "H", "R"])
        code = export(mod, backend="openscad", fn=32)
        assert "module bracket(L, W, H, R)" in code
        assert "$fn = 32;" in code
        assert "difference()" in code
        assert "translate" in code
