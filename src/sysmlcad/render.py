"""Image rendering backend (PNG, SVG) via the OpenSCAD CLI.

Produces 2D images of 3D shapes by first rendering to OpenSCAD source
and then compiling with ``openscad``.

On headless systems (no X display), the backend automatically starts a
virtual framebuffer (Xvfb) if available.

Prerequisites
-------------
- The ``openscad`` binary must be installed (``is_available()`` checks this).

If ``openscad`` is not available the backend still generates valid
OpenSCAD source (returned by ``render()``) and explains how to get an
image.

Usage
-----
::

    from sysmlcad import Box, export

    part = Box(100, 50, 30)

    # Export to PNG (requires openscad on PATH)
    export(part, backend="png", binary=True, filename="output.png",
           width=800, height=600)

    # Change view angle
    export(part, backend="png", binary=True, filename="top.png",
           camera=(0, 0, 0, 0, 0, 200))  # eye_x,eye_y,eye_z, ...
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from sysmlcad.backend import ShapeBackend, register_backend
from sysmlcad.ir import Shape


# ---------------------------------------------------------------------------
# Xvfb helper — start a virtual framebuffer on headless systems
# ---------------------------------------------------------------------------

_XVFB_PROCESS: subprocess.Popen | None = None


_XVFB_CANDIDATES = [
    "Xvfb",
    "/usr/bin/Xvfb",
    "/usr/local/bin/Xvfb",
    "/tmp/xvfb_extract/usr/bin/Xvfb",
]


def _find_xvfb() -> str | None:
    """Locate the Xvfb binary, searching common locations."""
    for candidate in _XVFB_CANDIDATES:
        path = shutil.which(candidate) or candidate
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _ensure_display() -> str | None:
    """If no DISPLAY is set and Xvfb is available, start one and return
    the display string.  Returns ``None`` if a display is already
    available or Xvfb cannot be started."""
    display = os.environ.get("DISPLAY", "")
    if display:
        return None  # display already available

    xvfb_path = _find_xvfb()
    if xvfb_path is None:
        return None

    global _XVFB_PROCESS
    try:
        proc = subprocess.Popen(
            [xvfb_path, ":99", "-screen", "0", "1280x960x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _XVFB_PROCESS = proc
        os.environ["DISPLAY"] = ":99"
        import time
        time.sleep(1)
        return ":99"
    except Exception:
        return None


def _cleanup_xvfb() -> None:
    global _XVFB_PROCESS
    if _XVFB_PROCESS is not None:
        try:
            _XVFB_PROCESS.terminate()
            _XVFB_PROCESS.wait(timeout=5)
        except Exception:
            try:
                _XVFB_PROCESS.kill()
            except Exception:
                pass
        _XVFB_PROCESS = None


import atexit
atexit.register(_cleanup_xvfb)


def _common_render(shape: Shape, **options) -> str:
    """Generate OpenSCAD source via the OpenSCAD backend."""
    from sysmlcad.openscad import OpenSCADBackend

    backend = OpenSCADBackend()
    return backend.render(shape, **options)


def _openscad_render(
    shape: Shape,
    output_ext: str,
    extra_args: list[str] | None = None,
    **options,
) -> bytes:
    """Render a shape to a binary image format via the openscad CLI.

    Parameters
    ----------
    shape : Shape
        Shape tree to render.
    output_ext : str
        Output file extension (``".png"``, ``".svg"``).
    extra_args : list[str] | None
        Extra CLI flags for openscad (e.g. ``--imgsize``).
    **options :
        Passed through to the OpenSCAD backend's ``render()``.

    Returns
    -------
    bytes
        The rendered image data.
    """
    if shutil.which("openscad") is None:
        raise RuntimeError(
            "openscad CLI not found on PATH -- install OpenSCAD "
            "(https://openscad.org) or use the 'openscad' backend "
            "to generate .scad and render manually:\n"
            f"  openscad -o output{output_ext} input.scad"
        )

    # Ensure a display is available (start Xvfb if needed)
    _ensure_display()

    scad_source = _common_render(shape, **options)

    tmp_dir = tempfile.mkdtemp(prefix="sysmlcad_render_")
    try:
        scad_path = Path(tmp_dir) / "input.scad"
        scad_path.write_text(scad_source, encoding="utf-8")

        out_path = Path(tmp_dir) / f"output{output_ext}"

        cmd = ["openscad"]
        if extra_args:
            cmd.extend(extra_args)
        cmd.extend(["-o", str(out_path), str(scad_path)])

        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=300,
        )

        return out_path.read_bytes()
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# PNG backend
# ---------------------------------------------------------------------------

@register_backend(name="png")
class PngBackend(ShapeBackend):
    """Render a Shape tree to a PNG image via OpenSCAD."""

    def render(self, shape: Shape, **options) -> str:
        """Return the intermediate OpenSCAD source."""
        return _common_render(shape, **options)

    def render_binary(self, shape: Shape, **options) -> bytes:
        """Render to PNG.

        Optional keyword arguments forwarded to the openscad CLI:

        * ``width``, ``height`` -- image dimensions (default 800×600)
        * ``camera`` -- 6-tuple ``(eye_x, eye_y, eye_z, center_x,
          center_y, center_z)``
        * ``colorscheme`` -- OpenSCAD color scheme name
          (e.g. ``"Nature"``, ``"Sunset"``, ``"Metallic"``)
        """
        extra = ["--viewall", "--autocenter"]

        w = options.get("width", 800)
        h = options.get("height", 600)
        extra.append(f"--imgsize={w},{h}")

        cs = options.get("colorscheme")
        if cs:
            extra.append(f"--colorscheme={cs}")

        camera = options.get("camera")
        if camera:
            extra.append(f"--camera={','.join(str(v) for v in camera)}")
        else:
            # Default 3/4-perspective from front-right-above
            extra.append("--camera=100,-150,80,0,0,0")

        return _openscad_render(
            shape,
            output_ext=".png",
            extra_args=extra,
            **options,
        )

    def mime_type(self) -> str:
        return "image/png"

    def file_extension(self) -> str:
        return ".png"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("openscad") is not None


# ---------------------------------------------------------------------------
# SVG backend
# ---------------------------------------------------------------------------

@register_backend(name="svg")
class SvgBackend(ShapeBackend):
    """Render a Shape tree to an SVG image via OpenSCAD."""

    def render(self, shape: Shape, **options) -> str:
        """Return the intermediate OpenSCAD source."""
        return _common_render(shape, **options)

    def render_binary(self, shape: Shape, **options) -> bytes:
        """Render to SVG (2D vector graphic).

        Optional keyword arguments:

        * ``camera`` -- 6-tuple ``(eye_x, eye_y, eye_z, center_x,
          center_y, center_z)``
        """
        extra = ["--viewall", "--autocenter"]
        camera = options.get("camera")
        if camera:
            extra.append(f"--camera={','.join(str(v) for v in camera)}")
        else:
            # Default 3/4-perspective from front-right-above
            extra.append("--camera=100,-150,80,0,0,0")

        return _openscad_render(
            shape,
            output_ext=".svg",
            extra_args=extra,
            **options,
        )

    def mime_type(self) -> str:
        return "image/svg+xml"

    def file_extension(self) -> str:
        return ".svg"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("openscad") is not None
