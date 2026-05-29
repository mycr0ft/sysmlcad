"""Abstract backend interface and registry.

Every backend implements ``ShapeBackend`` and registers via the class-level
``_registry`` or the ``register_backend`` decorator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from sysmlcad.ir import Shape


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_backend_registry: dict[str, type["ShapeBackend"]] = {}


def register_backend(cls: type["ShapeBackend"] | None = None, *,
                     name: str | None = None):
    """Decorator to register a backend class."""
    def _wrap(klass: type["ShapeBackend"]):
        key = name or klass.__name__.lower().replace("backend", "").strip("_")
        _backend_registry[key] = klass
        return klass
    if cls is not None:
        return _wrap(cls)
    return _wrap


def get_backend(name: str) -> type["ShapeBackend"]:
    """Look up a backend by name (case-insensitive)."""
    key = name.lower().replace("-", "").replace("_", "")
    for registered_name, backend_cls in _backend_registry.items():
        if registered_name == key:
            return backend_cls
    raise KeyError(f"No backend registered for {name!r}. "
                   f"Available: {list(_backend_registry.keys())}")


def list_backends() -> list[str]:
    """List all registered backend names."""
    return list(_backend_registry.keys())


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ShapeBackend(ABC):
    """A backend renders a Shape tree to a specific output format."""

    @abstractmethod
    def render(self, shape: Shape, **options) -> str:
        """Render a Shape tree to a string."""

    @abstractmethod
    def mime_type(self) -> str:
        """Return the MIME type of the output (e.g., 'text/x-openscad')."""

    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension (e.g., '.scad', '.step', '.stl')."""

    @staticmethod
    def is_available() -> bool:
        """Check if this backend's dependencies are available."""
        return True
