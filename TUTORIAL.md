# sysmlcad Tutorial

A step-by-step introduction to parametric CAD modeling with Python and
pluggable backends (OpenSCAD, Build123d, and more).

---

## 1. Primitives

Everything starts with a primitive shape:

```python
from sysmlcad import Box, Cylinder, Sphere, Cone, Torus

box = Box(100, 50, 30)           # Box(length, width, height)
cyl = Cylinder(30, 5)            # Cylinder(height, radius)
sph = Sphere(25)                 # Sphere(radius)
cone = Cone(20, 10, 3)           # Cone(height, bottom_radius, top_radius)
torus = Torus(50, 10)            # Torus(major_radius, minor_radius)
```

Export to OpenSCAD:

```python
from sysmlcad import export

print(export(box, backend="openscad"))
```

```
Box_1 = cube([100, 50, 30]);
result = Box_1;
```

Or to Build123d (generated Python source):

```python
print(export(box, backend="build123d"))
```

```python
from build123d import *
_box_1 = Box(100, 50, 30)
result = _box_1
```

---

## 2. CSG — Union, Difference, Intersection

Use Python operators to combine shapes:

```python
from sysmlcad import Box, Cylinder, export

box = Box(100, 50, 30)
hole = Cylinder(30, 5)

# Difference (subtraction)
part = box - hole

# Union (addition)
assembly = box + Cylinder(100, 10)

# Intersection
overlap = box * Sphere(60)

print(export(part, backend="openscad"))
```

```openscad
Box_1 = cube([100, 50, 30]);
Cylinder_2 = cylinder(h=30, r=5, center=true);
difference() {
    Box_1;
    Cylinder_2;
}
result = difference_result_3;
```

You can chain operations:

```python
result = Box(100, 50, 30) - Cylinder(30, 5) - Translate(Cylinder(30, 5), x=50)
```

> **Note**: The named classes `Union`, `Difference`, and `Intersection` are also
> available if you prefer to be explicit.

---

## 3. Parameters

Make designs parametric with `Parameter`:

```python
from sysmlcad import Parameter, Box, Cylinder, export

length = Parameter("L", 100)
width = Parameter("W", 50)
height = Parameter("H", 30)
hole_radius = Parameter("R", 5)

box = Box(length, width, height)
hole = Cylinder(height, hole_radius)
part = box - hole
```

When exported, the parameter values are resolved to their defaults.
For OpenSCAD, wrap in a `Module` to generate a parameterized module:

```python
from sysmlcad import Module

mod = Module(part, module_name="bracket",
             export_params=["L", "W", "H", "R"])
print(export(mod, backend="openscad"))
```

```openscad
module bracket(L, W, H, R) {
    Box_1 = cube([L, W, H]);
    Cylinder_2 = cylinder(h=H, r=R, center=true);
    difference() {
        Box_1;
        Cylinder_2;
    }
    result = difference_result_3;
}
bracket(L=100, W=50, H=30, R=5);
```

Parameters work in arithmetic expressions too:

```python
length = Parameter("L", 100)
box = Box(length, length / 2, length / 3)
```

---

## 4. Transforms

Move, rotate, scale, and mirror shapes:

```python
from sysmlcad import Box, Cylinder, Translate, Rotate, Scale, Mirror, export

# Translate
part = Translate(Box(10, 10, 10), x=5, y=10, z=15)

# Rotate around an axis (default Z)
part = Rotate(Cylinder(30, 5), angle=45)          # 45° around Z
part = Rotate(Cylinder(30, 5), angle=90, axis=(1, 0, 0))  # 90° around X

# RotateXYZ (three-axis rotation)
from sysmlcad import RotateXYZ
part = RotateXYZ(Cylinder(30, 5), x=30, y=45, z=0)

# Scale
part = Scale(Box(10, 10, 10), x=2, y=1, z=0.5)

# Mirror
part = Mirror(Box(10, 10, 10), plane="xy")
```

Transforms compose naturally with CSG:

```python
part = Box(100, 50, 30) - Translate(Cylinder(30, 5), x=50, y=25)
```

---

## 5. 2D to 3D

Create 2D profiles and extrude them:

```python
from sysmlcad import Circle, Rectangle, Polygon, Text, Extrude, Revolve, export

# Extrude a 2D profile
profile = Circle(30)
block = Extrude(profile, height=20)

# Revolve a 2D profile
profile = Rectangle(10, 20)
vase = Revolve(profile, angle=360)

# Text
from sysmlcad import Text
label = Extrude(Text("Hello", size=10), height=2)
```

OpenSCAD output for `Extrude(Circle(30), height=20)`:

```openscad
Circle_1 = circle(r=30);
linear_extrude(height=20) {
    Circle_1;
}
result = Extrude_2;
```

---

## 6. Modules

Group a shape tree into a reusable module:

```python
from sysmlcad import Box, Cylinder, Parameter, Module, export

length = Parameter("L", 100)
width = Parameter("W", 50)
height = Parameter("H", 30)
radius = Parameter("R", 5)

base = Box(length, width, height)
hole = Cylinder(height, radius)
part = base - Translate(hole, x=length / 2, y=width / 2)

mod = Module(part, module_name="bracket",
             export_params=["L", "W", "H", "R"])

# Export with custom $fn for OpenSCAD
print(export(mod, backend="openscad", fn=32))
```

```openscad
module bracket(L, W, H, R) {
    $fn = 32;
    Box_1 = cube([L, W, H]);
    Cylinder_2 = cylinder(h=H, r=R);
    difference() {
        Box_1;
        Cylinder_2;
    }
    result = difference_result_3;
}
bracket(L=100, W=50, H=30, R=5);
```

The `export_params` controls which parameters become function arguments.
Parameters not listed are inlined as their default values.

---

## 7. Assembly

Compose multiple shapes into a named assembly with relative placement:

```python
from sysmlcad import Assembly, Box, Cylinder, Sphere, export

assy = Assembly(name="robot_arm")
base = Box(100, 50, 30)
joint = Sphere(20)
arm = Cylinder(80, 10)

assy.place(base)
assy.place(joint, z=30)      # positioned relative to parent
assy.place(arm, z=30 + 20)   # on top of joint

print(export(assy, backend="openscad"))
```

```openscad
Box_1 = cube([100, 50, 30]);
Sphere_2 = sphere(r=20);
translate([0, 0, 30]) {
    Sphere_2;
}
Cylinder_3 = cylinder(h=80, r=10);
translate([0, 0, 50]) {
    Cylinder_3;
}
result = Union_4;
```

---

## 8. Appearance

Add colors for visualization:

```python
from sysmlcad import Box, Color, export

box = Box(100, 50, 30)
red_box = Color(box, "Red")
print(export(red_box, backend="openscad"))
```

```openscad
Box_1 = cube([100, 50, 30]);
color("Red") {
    Box_1;
}
result = Color_2;
```

---

## 9. Units

Use `pint` quantities for physical dimensions:

```python
import pint
from sysmlcad import Box, export

ureg = pint.UnitRegistry()

# Dimensions in millimeters
box = Box(100 * ureg.mm, 50 * ureg.mm, 30 * ureg.mm)

# Dimensions in meters (auto-converted to mm)
box = Box(1 * ureg.m, 0.5 * ureg.m, 0.3 * ureg.m)

# Mixed units
box = Box(1 * ureg.m, 500 * ureg.mm, 0.3 * ureg.m)

print(export(box, backend="openscad"))  # all in mm
```

---

## 10. Picking a Backend

| Backend | Output format | Requires | Best for |
|---------|--------------|----------|----------|
| `"openscad"` | `.scad` | — | Visualization, manual tweaking |
| `"build123d"` | `.py` | — | Programmatic CAD with build123d |
| `"stl"` | `.stl` | `openscad` CLI | 3D printing, mesh export |
| `"step"` | `.step` | `build123d` | CAD interchange (ISO 10303) |
| `"png"` | `.png` | `openscad` CLI | Rendered images |
| `"svg"` | `.svg` | `openscad` CLI | 2D vector graphics |

List available backends:

```python
from sysmlcad import list_backends, get_backend

print(list_backends())
# ['openscad', 'build123d', 'stl', 'step', 'png', 'svg']
b = get_backend("build123d")()
print(b.mime_type())              # "text/x-python"
print(b.file_extension())         # ".py"
```

Every backend's ``render()`` always works (returns generated source code).
Binary formats (STL, STEP, PNG, SVG) additionally support ``binary=True``,
which requires the tool listed above:

```python
export(part, backend="openscad", filename="part.scad")
export(part, backend="build123d", filename="part.py")

# Binary formats (only if the tool is installed)
export(part, backend="stl",  binary=True, filename="part.stl")
export(part, backend="step", binary=True, filename="part.step")
export(part, backend="png",  binary=True, filename="part.png",
       width=1280, height=960)
export(part, backend="svg",  binary=True, filename="part.svg")
```

Check availability at runtime:

```python
from sysmlcad import get_backend

png = get_backend("png")()
if png.is_available():
    export(part, backend="png", binary=True, filename="part.png")
else:
    print("Install openscad to render images")
```

---

## 11. Full Example — Parametric Bracket

```python
from sysmlcad import (
    Box, Cylinder, Translate, Parameter, Module, export,
)

# -- Parameters ---------------------------------------------------------------
length = Parameter("L", 100)
width  = Parameter("W", 50)
height = Parameter("H", 30)
radius = Parameter("R", 5)

# -- Shape --------------------------------------------------------------------
base = Box(length, width, height)
hole = Cylinder(height, radius)

# Center the hole
part = base - Translate(hole, x=length / 2, y=width / 2)

# -- Module (for OpenSCAD) ----------------------------------------------------
mod = Module(part, module_name="bracket",
             export_params=["L", "W", "H", "R"])

# -- Export -------------------------------------------------------------------
print(export(mod, backend="openscad", fn=32))
```

Save the output to a file and open it in OpenSCAD to see the result.
Drag the sliders for `L`, `W`, `H`, `R` to change the design in real time.

---

## 12. SysML Bridge

The ``sysml_bridge`` module converts SysML v2 models to CAD shapes
using a convention-based mapping.

Load a ``.sysml`` file and export to OpenSCAD in one call:

```python
from sysmlcad.sysml_bridge import sysml_file_to_cad

code = sysml_file_to_cad("examples/bracket.sysml", backend="openscad")
print(code)
```

Example ``.sysml`` files live in ``examples/``:

| File | Description |
|------|-------------|
| `simple_box.sysml` | A single box primitive |
| `bracket.sysml` | Bracket with centered hole (CSG difference) |
| `flange.sysml` | Flange plate with 4 bolt holes |
| `assembly.sysml` | Three parts joined in an assembly |

Render all examples to images:

```bash
poetry run python examples/render_all.py
poetry run python examples/render_all.py --backend png --width 1280 --height 960
```

The bridge convention maps SysML attributes to CAD parameters:

| Attributes | Shape |
|-----------|-------|
| `length`, `width`, `height` | `Box` |
| `height`, `radius` | `Cylinder` |
| `radius` (only) | `Sphere` |
| `height`, `radius1`, `radius2` | `Cone` |
| `majorRadius`, `minorRadius` | `Torus` |
| `operator` + child parts | CSG (union/difference/intersection) |
| `x`, `y`, `z` | `Translate` |

---

## 13. Next Steps

- Browse the source at `src/sysmlcad/ir.py` for all supported shape types
- Check `src/sysmlcad/expression.py` for the expression system
- Add a new backend by subclassing `ShapeBackend` and using `@register_backend`
- See the test suite at `tests/test_cad.py` for more examples
