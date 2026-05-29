"""STL (stereolithography) backend.

Generates an STL file by first rendering to OpenSCAD and then
compiling with the ``openscad`` command-line tool.

Prerequisites
-------------
- The ``openscad`` binary must be installed (``is_available()`` checks this).

If ``openscad`` is not available the backend still generates valid
OpenSCAD source (returned by ``render()``) and explains how to get STL.

Usage
-----
::

    from sysmlcad import Box, export

    part = Box(100, 50, 30)

    # Export to STL (requires openscad on PATH)
    export(part, backend="stl", binary=True, filename="part.stl")

    # Just generate the intermediate .scad (openscad not needed)
    scad = export(part, backend="stl")
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sysmlcad.backend import ShapeBackend, register_backend
from sysmlcad.ir import Shape


@register_backend(name="stl")
class StlBackend(ShapeBackend):
    """Compile a Shape tree to STL via OpenSCAD."""

    def render(self, shape: Shape, **options) -> str:
        """Return the intermediate OpenSCAD source for this shape.

        Always succeeds (does not require ``openscad``).
        """
        from sysmlcad.openscad import OpenSCADBackend

        backend = OpenSCADBackend()
        return backend.render(shape, **options)

    def render_binary(self, shape: Shape, **options) -> bytes:
        """Compile to STL via the ``openscad`` CLI (must be installed).

        Raises
        ------
        RuntimeError
            If ``openscad`` is not found on ``PATH``.
        """
        if not self.is_available():
            msg = (
                "openscad CLI not found on PATH -- install OpenSCAD "
                "(https://openscad.org) or use the 'openscad' backend "
                "to generate .scad and compile manually:\n"
                "  openscad -o output.stl input.scad"
            )
            raise RuntimeError(msg)

        # Generate the .scad source
        scad_source = self.render(shape, **options)

        # Write to a temporary .scad file
        tmp_dir = tempfile.mkdtemp(prefix="sysmlcad_stl_")
        try:
            scad_path = Path(tmp_dir) / "input.scad"
            scad_path.write_text(scad_source, encoding="utf-8")

            stl_path = Path(tmp_dir) / "output.stl"
            subprocess.run(
                ["openscad", "-o", str(stl_path), str(scad_path)],
                capture_output=True,
                check=True,
                timeout=300,
            )

            return stl_path.read_bytes()
        finally:
            # Clean up temp directory
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def mime_type(self) -> str:
        return "model/stl"

    def file_extension(self) -> str:
        return ".stl"

    @staticmethod
    def is_available() -> bool:
        """Check if ``openscad`` is available on PATH."""
        return shutil.which("openscad") is not None
