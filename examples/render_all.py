#!/usr/bin/env python3
"""Render all ``examples/*.sysml`` models to PNG images.

Requires the ``openscad`` CLI for actual image rendering.  If ``openscad``
is not available, intermediate ``.scad`` files are saved instead.

Usage
-----
::

    poetry run python examples/render_all.py
    poetry run python examples/render_all.py --backend png --width 1280 --height 960
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sysmlcad.sysml_bridge import sysml_file_to_cad

HERE = Path(__file__).resolve().parent


def render_example(
    sysml_path: Path,
    out_dir: Path,
    backend: str = "png",
    width: int = 800,
    height: int = 600,
    camera: tuple[float, ...] | None = None,
    colorscheme: str | None = None,
) -> str | None:
    """Render one .sysml file to an image.

    Returns the path to the output file, or ``None`` on failure.
    """
    # Generate the intermediate OpenSCAD source via the bridge
    stem = sysml_path.stem

    # Check if the image backend is available
    from sysmlcad import get_backend

    try:
        bkls = get_backend(backend)
    except KeyError:
        print(f"  Unknown backend {backend!r}")
        return None

    if not bkls().is_available():
        # Fallback: save .scad file with instructions
        scad_path = out_dir / f"{stem}.scad"
        scad_source = sysml_file_to_cad(str(sysml_path), backend="openscad")
        scad_path.write_text(scad_source)
        print(f"  {stem}: saved .scad to {scad_path.name}")
        print(f"         (install openscad and run: "
              f"openscad -o {stem}.png {scad_path.name})")
        return str(scad_path)

    # Render to image
    ext = bkls().file_extension()
    out_path = out_dir / f"{stem}{ext}"

    from sysmlcad import export as _export
    from sysmlcad.sysml_bridge import model_to_assembly
    import sysmlpy

    with open(str(sysml_path)) as f:
        model = sysmlpy.load(f)
    assembly = model_to_assembly(model)
    if assembly is None:
        print(f"  {stem}: no convertible parts found")
        return None

    kwargs: dict = {
        "binary": True,
        "filename": str(out_path),
        "width": width,
        "height": height,
    }
    if camera:
        kwargs["camera"] = camera
    if colorscheme:
        kwargs["colorscheme"] = colorscheme

    _export(assembly, backend=backend, **kwargs)
    size_kb = out_path.stat().st_size / 1024
    print(f"  {stem}: {out_path.name} ({size_kb:.0f} KiB)")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(
        description="Render SysML CAD examples to images",
    )
    parser.add_argument(
        "--backend", default="png",
        choices=["png", "svg"],
        help="Image backend (default: png)",
    )
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument(
        "--camera", type=float, nargs=6, metavar=("X", "Y", "Z", "CX", "CY", "CZ"),
        default=None,
        help="Camera position: eye_x eye_y eye_z center_x center_y center_z",
    )
    parser.add_argument(
        "--colorscheme",
        default=None,
        help="OpenSCAD color scheme (e.g. Nature, Sunset, Metallic)",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="Output directory (default: examples/)",
    )
    args = parser.parse_args()

    out_dir = Path(args.outdir) if args.outdir else HERE
    out_dir.mkdir(parents=True, exist_ok=True)

    sysml_files = sorted(HERE.glob("*.sysml"))
    if not sysml_files:
        print("No .sysml files found")
        return

    print(f"Rendering {len(sysml_files)} model(s) to {out_dir}/")
    print(f"  Backend:     {args.backend}")
    print(f"  Resolution:  {args.width}x{args.height}")
    print()

    ok = 0
    for path in sysml_files:
        result = render_example(
            path,
            out_dir=out_dir,
            backend=args.backend,
            width=args.width,
            height=args.height,
            camera=args.camera,
            colorscheme=args.colorscheme,
        )
        if result:
            ok += 1

    print()
    print(f"Done: {ok}/{len(sysml_files)} succeeded")


if __name__ == "__main__":
    main()
