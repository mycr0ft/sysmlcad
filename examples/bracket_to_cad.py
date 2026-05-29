#!/usr/bin/env python3
"""Demo: SysMLv2 → CAD pipeline via the sysmlcad bridge.

Runs each ``examples/*.sysml`` file through the bridge and prints the
generated OpenSCAD and Build123d output.

Usage::

    poetry run python examples/bracket_to_cad.py
"""

from pathlib import Path

from sysmlcad.sysml_bridge import sysml_file_to_cad

HERE = Path(__file__).resolve().parent
EXAMPLES = sorted(HERE.glob("*.sysml"))


def show_separator(label: str) -> None:
    width = 72
    dashes = (width - len(label) - 2) // 2
    print()
    print("=" * width)
    print(f"{'─' * dashes} {label} {'─' * dashes}")
    print("=" * width)


def show_both_backends(path: Path) -> None:
    """Print both OpenSCAD and Build123d output for a .sysml file."""
    show_separator(path.name)

    print(f"\n--- OpenSCAD ---")
    try:
        code = sysml_file_to_cad(str(path), backend="openscad")
        print(code if code else "  (no convertible parts)")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\n--- Build123d ---")
    try:
        code = sysml_file_to_cad(str(path), backend="build123d")
        print(code if code else "  (no convertible parts)")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    if not EXAMPLES:
        print("No .sysml files found in examples/")
        return

    print(f"Found {len(EXAMPLES)} example file(s)")
    for path in EXAMPLES:
        show_both_backends(path)


if __name__ == "__main__":
    main()
