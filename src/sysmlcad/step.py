"""STEP (ISO 10303-21) backend.

Generates a STEP file by first rendering to build123d Python code and
then executing it with the ``build123d`` library.

Prerequisites
-------------
- The ``build123d`` package must be installed (``is_available()`` checks this).
- build123d wraps the OpenCascade Technology (OCCT) kernel.

If ``build123d`` is not available the backend still generates valid
Python source (returned by ``render()``) that the user can run manually.

Usage
-----
::

    from sysmlcad import Box, Cylinder, export

    part = Box(100, 50, 30) - Cylinder(30, 5)

    # Export to STEP (requires build123d)
    export(part, backend="step", binary=True, filename="part.step")

    # Just generate the intermediate .py (build123d not needed)
    py_source = export(part, backend="step")
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sysmlcad.backend import ShapeBackend, register_backend
from sysmlcad.ir import Shape


def _build123d_importable() -> bool:
    """Check if build123d can be imported."""
    try:
        import build123d  # noqa: F401
        return True
    except ImportError:
        return False


# Wrapper template: takes user-generated build123d code, appends export step.
_STEP_WRAPPER = """\
import build123d
{build123d_code}

# Export result variable to STEP
build123d.export_step(result, "{output_path}")
"""


@register_backend(name="step")
class StepBackend(ShapeBackend):
    """Compile a Shape tree to STEP via build123d."""

    def render(self, shape: Shape, **options) -> str:
        """Return the intermediate build123d Python source for this shape.

        Always succeeds (does not require ``build123d``).
        """
        from sysmlcad.build123d import Build123dBackend

        backend = Build123dBackend()
        return backend.render(shape, **options)

    def render_binary(self, shape: Shape, **options) -> bytes:
        """Compile to STEP via the ``build123d`` library.

        Raises
        ------
        RuntimeError
            If ``build123d`` is not installed.
        """
        if not self.is_available():
            msg = (
                "build123d not installed -- pip install build123d, or use "
                "the 'build123d' backend to generate .py and run it manually."
            )
            raise RuntimeError(msg)

        py_source = self.render(shape, **options)

        tmp_dir = tempfile.mkdtemp(prefix="sysmlcad_step_")
        try:
            step_path = Path(tmp_dir) / "output.step"
            py_path = Path(tmp_dir) / "export_step.py"

            wrapper = _STEP_WRAPPER.format(
                build123d_code=py_source,
                output_path=str(step_path),
            )
            py_path.write_text(wrapper, encoding="utf-8")

            subprocess.run(
                [self._python(), str(py_path)],
                capture_output=True,
                check=True,
                timeout=300,
            )

            return step_path.read_bytes()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def mime_type(self) -> str:
        return "model/step"

    def file_extension(self) -> str:
        return ".step"

    @staticmethod
    def is_available() -> bool:
        return _build123d_importable()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _python() -> str:
        """Return the path to the current Python interpreter."""
        import sys
        return sys.executable
