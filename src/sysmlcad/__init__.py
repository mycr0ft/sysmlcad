"""sysmlcad -- parametric CAD shape modeling with pluggable backends.

Provides a backend-agnostic Shape IR (Intermediate Representation)
that can be rendered to multiple CAD formats (OpenSCAD, CadQuery, Build123d,
STEP, STL) via pluggable backends.

Quick start:

    from sysmlcad import Box, Cylinder, Sphere, Difference, Union, \
        Translate, Rotate, Parameter, export

    length = Parameter("length", 100)
    box = Box(length, 50, 30)
    hole = Cylinder(30, 5)
    part = box - Translate(hole, x=50, y=25)

    # Export to OpenSCAD
    scad_code = export(part, backend="openscad")

    # Export to file
    export(part, backend="openscad", filename="part.scad")
"""

from sysmlcad.ir import (
    Shape,
    # Primitives -- 3D
    Box, Cylinder, Sphere, Cone, Torus, Wedge, Prism,
    # Primitives -- 2D
    Polygon, Circle, Rectangle, Text,
    # 2D -> 3D
    Extrude, Revolve, Loft, Sweep,
    # Transforms
    Translate, Rotate, RotateXYZ, Scale, Mirror,
    # CSG
    Union, Difference, Intersection,
    # Modules
    Module, ModuleRef,
    # Appearance
    Color, Modifier,
    # Hull / Minkowski / Offset
    Hull, Minkowski, Offset,
    # Assembly
    Assembly, Connection,
    # Parameter system
    Parameter, make_param,
)

from sysmlcad.backend import (
    ShapeBackend,
    get_backend,
    list_backends,
    register_backend,
)

from sysmlcad.expression import (
    Expression, Literal, ParameterRef, BinaryOp, UnaryOp, FunctionCall,
)

from sysmlcad import openscad  # noqa: F401 -- import to register backend
from sysmlcad import build123d  # noqa: F401 -- import to register backend


def export(shape: Shape, backend: str = "openscad", **options) -> str:
    """Render a Shape tree using the named backend.

    Parameters
    ----------
    shape : Shape
        Root of the shape tree to render.
    backend : str
        Backend name ('openscad', 'cadquery', 'build123d', 'step', 'stl').
    **options :
        Passed to the backend's ``render()`` method.

    Returns
    -------
    str
        Rendered output (OpenSCAD source, CadQuery source, etc.).

    If ``filename`` is provided in options, also writes to that file.
    """
    backend_cls = get_backend(backend)
    inst = backend_cls()
    result = inst.render(shape, **options)
    filename = options.get("filename")
    if filename:
        import pathlib
        pathlib.Path(filename).write_text(result)
    return result


__all__ = [
    # IR
    "Shape",
    "Box", "Cylinder", "Sphere", "Cone", "Torus", "Wedge", "Prism",
    "Polygon", "Circle", "Rectangle", "Text",
    "Extrude", "Revolve", "Loft", "Sweep",
    "Translate", "Rotate", "RotateXYZ", "Scale", "Mirror",
    "Union", "Difference", "Intersection",
    "Module", "ModuleRef",
    "Color", "Modifier",
    "Hull", "Minkowski", "Offset",
    "Assembly", "Connection",
    "Parameter", "make_param",
    # Expressions
    "Expression", "Literal", "ParameterRef", "BinaryOp", "UnaryOp",
    "FunctionCall",
    # Backend
    "ShapeBackend", "get_backend", "list_backends", "register_backend",
    # Export
    "export",
]
