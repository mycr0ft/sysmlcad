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


# ===================================================================
# Build123d Backend tests
# ===================================================================

class TestBuild123dBackend:
    def test_backend_registered(self):
        names = list_backends()
        assert "build123d" in names

    def test_mime_type(self):
        backend = get_backend("build123d")()
        assert backend.mime_type() == "text/x-python"

    def test_file_extension(self):
        backend = get_backend("build123d")()
        assert backend.file_extension() == ".py"

    def test_is_available(self):
        backend = get_backend("build123d")()
        # build123d not installed in test env, should be False
        # (we only test code generation, not execution)
        from sysmlcad.build123d import Build123dBackend
        # just check the method exists and returns bool
        result = backend.is_available()
        assert isinstance(result, bool)

    def test_export_box(self):
        box = Box(100, 50, 30)
        code = export(box, backend="build123d")
        assert "from build123d import *" in code
        assert "Box(100, 50, 30)" in code
        assert "result = " in code

    def test_export_cylinder(self):
        cyl = Cylinder(40, 5)
        code = export(cyl, backend="build123d")
        assert "Cylinder(radius=5, height=40)" in code

    def test_export_sphere(self):
        sphere = Sphere(25)
        code = export(sphere, backend="build123d")
        assert "Sphere(radius=25)" in code

    def test_export_cone(self):
        cone = Cone(20, 10, 3)
        code = export(cone, backend="build123d")
        assert "Cone(bottom_radius=10, top_radius=3, height=20)" in code

    def test_export_torus(self):
        torus = Torus(50, 10)
        code = export(torus, backend="build123d")
        assert "Torus(major_radius=50, minor_radius=10)" in code

    def test_export_union(self):
        a = Box(10, 10, 10)
        b = Cylinder(10, 5)
        union = a + b
        code = export(union, backend="build123d")
        assert " + " in code

    def test_export_difference(self):
        box = Box(100, 50, 30)
        hole = Cylinder(30, 5)
        part = box - hole
        code = export(part, backend="build123d")
        assert " - " in code

    def test_export_translate(self):
        box = Box(10, 10, 10)
        t = Translate(box, x=5, y=10, z=15)
        code = export(t, backend="build123d")
        assert "Pos(5, 10, 15)" in code

    def test_export_with_parameter(self):
        length = Parameter("L", 100)
        box = Box(length, 50, 30)
        code = export(box, backend="build123d")
        assert "100" in code

    def test_export_module_definition(self):
        shape = Box(100, 50, 30, name="base")
        mod = Module(shape, module_name="base_plate")
        code = export(mod, backend="build123d")
        assert "def base_plate():" in code
        assert "Box(100, 50, 30)" in code
        assert "return " in code

    def test_export_module_with_params(self):
        shape = Box(Parameter("L", 100), Parameter("W", 50), Parameter("H", 30))
        mod = Module(shape, module_name="box_module",
                     export_params=["L", "W", "H"])
        code = export(mod, backend="build123d")
        assert "def box_module(L, W, H):" in code
        assert "Box(L, W, H)" in code

    def test_export_assembly(self):
        assembly = Assembly(name="bracket")
        bracket = Box(100, 50, 30)
        assembly.place(bracket)
        cap = Sphere(50)
        assembly.place(cap, z=30)
        code = export(assembly, backend="build123d")
        assert " + " in code

    def test_export_with_units_mm(self):
        ureg = pint.UnitRegistry()
        box = Box(100 * ureg.mm, 50 * ureg.mm, 30 * ureg.mm)
        code = export(box, backend="build123d")
        assert "Box(100, 50, 30)" in code

    def test_export_with_units_m_to_mm(self):
        ureg = pint.UnitRegistry()
        box = Box(1 * ureg.m, 0.5 * ureg.m, 0.3 * ureg.m)
        code = export(box, backend="build123d")
        assert "1000" in code  # converted to mm


# ===================================================================
# SysML bridge tests
# ===================================================================

class TestSysmlBridge:
    """Test the convention-based SysMLv2 → Shape IR bridge."""

    BOX_SYSML = """\
package Test {
    part myBox {
        attribute length = 100.0;
        attribute width = 50.0;
        attribute height = 30.0;
    }
}"""

    CYL_SYSML = """\
package Test {
    part myCyl {
        attribute height = 40.0;
        attribute radius = 5.0;
    }
}"""

    SPHERE_SYSML = """\
package Test {
    part mySphere {
        attribute radius = 25.0;
    }
}"""

    CONE_SYSML = """\
package Test {
    part myCone {
        attribute height = 20.0;
        attribute radius1 = 10.0;
        attribute radius2 = 3.0;
    }
}"""

    TORUS_SYSML = """\
package Test {
    part myTorus {
        attribute majorRadius = 50.0;
        attribute minorRadius = 10.0;
    }
}"""

    TRANSLATE_SYSML = """\
package Test {
    part myBox {
        attribute length = 10.0;
        attribute width = 10.0;
        attribute height = 10.0;
        attribute x = 5.0;
        attribute y = 10.0;
        attribute z = 15.0;
    }
}"""

    DIFFERENCE_SYSML = """\
package Test {
    part bracket {
        attribute operator = "difference";
        part base {
            attribute length = 100.0;
            attribute width = 50.0;
            attribute height = 30.0;
        }
        part hole {
            attribute height = 30.0;
            attribute radius = 5.0;
        }
    }
}"""

    UNION_SYSML = """\
package Test {
    part joined {
        attribute operator = "union";
        part a {
            attribute length = 10.0;
            attribute width = 10.0;
            attribute height = 10.0;
        }
        part b {
            attribute radius = 5.0;
        }
        part c {
            attribute length = 20.0;
            attribute width = 5.0;
            attribute height = 5.0;
        }
    }
}"""

    INTERSECTION_SYSML = """\
package Test {
    part overlap {
        attribute operator = "intersection";
        part a {
            attribute length = 10.0;
            attribute width = 10.0;
            attribute height = 10.0;
        }
        part b {
            attribute radius = 8.0;
        }
    }
}"""

    ASSEMBLY_SYSML = """\
package Test {
    part base {
        attribute length = 100.0;
        attribute width = 80.0;
        attribute height = 10.0;
    }
    part block {
        attribute length = 40.0;
        attribute width = 30.0;
        attribute height = 50.0;
        attribute x = 30.0;
        attribute y = 25.0;
    }
}"""

    # -- primitives ----------------------------------------------------------

    def test_box(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.BOX_SYSML, backend="openscad")
        assert "cube([100, 50, 30])" in code

    def test_cylinder(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.CYL_SYSML, backend="openscad")
        assert "cylinder(h=40, r=5)" in code

    def test_sphere(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.SPHERE_SYSML, backend="openscad")
        assert "sphere(r=25)" in code

    def test_cone(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.CONE_SYSML, backend="openscad")
        assert "cylinder(h=20, r1=10, r2=3)" in code

    def test_torus(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.TORUS_SYSML, backend="openscad")
        # OpenSCAD renders torus via rotate_extrude
        assert "rotate_extrude" in code or "translate" in code

    # -- transforms ----------------------------------------------------------

    def test_translate(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.TRANSLATE_SYSML, backend="openscad")
        assert "translate([5, 10, 15])" in code
        assert "cube([10, 10, 10])" in code

    # -- CSG ----------------------------------------------------------------

    def test_difference(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.DIFFERENCE_SYSML, backend="openscad")
        assert "difference()" in code
        assert "cube([100, 50, 30])" in code
        assert "cylinder(h=30, r=5)" in code

    def test_union(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.UNION_SYSML, backend="openscad")
        assert "union()" in code

    def test_intersection(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.INTERSECTION_SYSML, backend="openscad")
        assert "intersection()" in code

    # -- assembly -----------------------------------------------------------

    def test_assembly(self):
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.ASSEMBLY_SYSML, backend="openscad")
        assert "cube([100, 80, 10])" in code
        assert "cube([40, 30, 50])" in code
        assert "translate([30, 25, 0])" in code

    def test_all_backends(self):
        """Every .sysml example should produce valid output in both backends."""
        from sysmlcad.sysml_bridge import sysml_to_cad
        sources = [
            self.BOX_SYSML,
            self.CYL_SYSML,
            self.SPHERE_SYSML,
            self.CONE_SYSML,
            self.TORUS_SYSML,
            self.TRANSLATE_SYSML,
            self.DIFFERENCE_SYSML,
            self.UNION_SYSML,
            self.INTERSECTION_SYSML,
        ]
        for src in sources:
            openscad = sysml_to_cad(src, backend="openscad")
            assert openscad != ""
            build123d = sysml_to_cad(src, backend="build123d")
            assert build123d != ""

    # -- model inspection with part_to_shape / model_to_shapes --------------

    def test_part_to_shape_box(self):
        import sysmlpy
        from sysmlcad.sysml_bridge import part_to_shape
        model = sysmlpy.loads(self.BOX_SYSML)
        shape = part_to_shape(model.packages[0].parts[0])
        assert shape is not None
        assert shape.type == "Box"

    def test_part_to_shape_cylinder(self):
        import sysmlpy
        from sysmlcad.sysml_bridge import part_to_shape
        model = sysmlpy.loads(self.CYL_SYSML)
        shape = part_to_shape(model.packages[0].parts[0])
        assert shape is not None
        assert shape.type == "Cylinder"

    def test_part_to_shape_translate(self):
        import sysmlpy
        from sysmlcad.sysml_bridge import part_to_shape
        model = sysmlpy.loads(self.TRANSLATE_SYSML)
        shape = part_to_shape(model.packages[0].parts[0])
        assert shape is not None
        assert shape.type == "Translate"

    def test_part_to_shape_difference(self):
        import sysmlpy
        from sysmlcad.sysml_bridge import part_to_shape
        model = sysmlpy.loads(self.DIFFERENCE_SYSML)
        shape = part_to_shape(model.packages[0].parts[0])
        assert shape is not None
        assert shape.type == "Difference"

    def test_model_to_shapes(self):
        import sysmlpy
        from sysmlcad.sysml_bridge import model_to_shapes
        model = sysmlpy.loads(self.ASSEMBLY_SYSML)
        shapes = model_to_shapes(model)
        assert len(shapes) == 2  # base and block (both top-level parts)

    def test_sysml_to_cad_empty(self):
        """A model with no convertible parts returns empty string."""
        from sysmlcad.sysml_bridge import sysml_to_cad
        source = "package Empty { part def AbstractPart; }"
        code = sysml_to_cad(source, backend="openscad")
        assert code == ""

    def test_build123d_output(self):
        """Verify build123d code is generated without errors."""
        from sysmlcad.sysml_bridge import sysml_to_cad
        code = sysml_to_cad(self.BOX_SYSML, backend="build123d")
        assert "Box(100, 50, 30)" in code


# ===================================================================
# STL and STEP backend tests
# ===================================================================

class TestStlBackend:
    def test_registered(self):
        names = list_backends()
        assert "stl" in names

    def test_mime_type(self):
        backend = get_backend("stl")()
        assert backend.mime_type() == "model/stl"

    def test_file_extension(self):
        backend = get_backend("stl")()
        assert backend.file_extension() == ".stl"

    def test_is_available(self):
        # openscad CLI not installed in test env
        backend = get_backend("stl")()
        assert isinstance(backend.is_available(), bool)

    def test_render_returns_scad(self):
        """Text render returns OpenSCAD source."""
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        code = export(box, backend="stl")
        assert isinstance(code, str)
        assert "cube" in code

    def test_render_with_csg(self):
        from sysmlcad import Box, Cylinder, export
        part = Box(100, 50, 30) - Cylinder(30, 5)
        code = export(part, backend="stl")
        assert "difference" in code or "cube" in code

    def test_render_binary_raises_when_unavailable(self):
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        backend = get_backend("stl")()
        if not backend.is_available():
            import pytest
            with pytest.raises(RuntimeError, match="openscad CLI not found"):
                export(box, backend="stl", binary=True)

    def test_export_to_file_text(self):
        """Writing .scad to file works when compilation not available."""
        import tempfile, pathlib
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        with tempfile.NamedTemporaryFile(suffix=".scad", delete=False) as f:
            path = f.name
        try:
            export(box, backend="stl", filename=path)
            content = pathlib.Path(path).read_text()
            assert "cube" in content
        finally:
            pathlib.Path(path).unlink(missing_ok=True)


class TestStepBackend:
    def test_registered(self):
        names = list_backends()
        assert "step" in names

    def test_mime_type(self):
        backend = get_backend("step")()
        assert backend.mime_type() == "model/step"

    def test_file_extension(self):
        backend = get_backend("step")()
        assert backend.file_extension() == ".step"

    def test_is_available(self):
        backend = get_backend("step")()
        assert isinstance(backend.is_available(), bool)

    def test_render_returns_python(self):
        """Text render returns build123d Python source."""
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        code = export(box, backend="step")
        assert isinstance(code, str)
        assert "Box" in code

    def test_render_with_csg(self):
        from sysmlcad import Box, Cylinder, export
        part = Box(100, 50, 30) - Cylinder(30, 5)
        code = export(part, backend="step")
        assert "Box" in code

    def test_render_binary_raises_when_unavailable(self):
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        backend = get_backend("step")()
        if not backend.is_available():
            import pytest
            with pytest.raises(RuntimeError, match="build123d not installed"):
                export(box, backend="step", binary=True)

    def test_export_to_file_text(self):
        """Writing .py to file works when compilation not available."""
        import tempfile, pathlib
        from sysmlcad import Box, export
        box = Box(100, 50, 30)
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            path = f.name
        try:
            export(box, backend="step", filename=path)
            content = pathlib.Path(path).read_text()
            assert "Box" in content
        finally:
            pathlib.Path(path).unlink(missing_ok=True)


# ===================================================================
# Image rendering (PNG / SVG) backend tests
# ===================================================================

class TestPngBackend:
    def test_registered(self):
        assert "png" in list_backends()

    def test_mime_type(self):
        backend = get_backend("png")()
        assert backend.mime_type() == "image/png"

    def test_file_extension(self):
        backend = get_backend("png")()
        assert backend.file_extension() == ".png"

    def test_is_available(self):
        backend = get_backend("png")()
        assert isinstance(backend.is_available(), bool)

    def test_render_returns_scad(self):
        box = Box(100, 50, 30)
        code = export(box, backend="png")
        assert isinstance(code, str)
        assert "cube" in code

    def test_render_binary_raises_when_unavailable(self):
        box = Box(100, 50, 30)
        backend = get_backend("png")()
        if not backend.is_available():
            with pytest.raises(RuntimeError, match="openscad CLI not found"):
                export(box, backend="png", binary=True)


class TestSvgBackend:
    def test_registered(self):
        assert "svg" in list_backends()

    def test_mime_type(self):
        backend = get_backend("svg")()
        assert backend.mime_type() == "image/svg+xml"

    def test_file_extension(self):
        backend = get_backend("svg")()
        assert backend.file_extension() == ".svg"

    def test_is_available(self):
        backend = get_backend("svg")()
        assert isinstance(backend.is_available(), bool)

    def test_render_returns_scad(self):
        box = Box(100, 50, 30)
        code = export(box, backend="svg")
        assert isinstance(code, str)
        assert "cube" in code

    def test_render_binary_raises_when_unavailable(self):
        box = Box(100, 50, 30)
        backend = get_backend("svg")()
        if not backend.is_available():
            with pytest.raises(RuntimeError, match="openscad CLI not found"):
                export(box, backend="svg", binary=True)
