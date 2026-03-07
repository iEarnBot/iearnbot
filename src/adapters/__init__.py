"""
adapters/__init__.py — Adapter registry for iEarn.Bot.

Usage
-----
    from adapters import load_adapter

    pm = load_adapter("polymarket")
    pm.smoke_test()

Dynamic loading
---------------
All *_adapter.py files in this directory are auto-discovered and registered.
Manually registered adapters (via register_adapter) take precedence.

Extending
---------
    from adapters import register_adapter
    from my_pkg.my_adapter import MyAdapter

    register_adapter("myplatform", MyAdapter)
    adapter = load_adapter("myplatform")

Generating new adapters
-----------------------
    from adapters.generator import generate_adapter

    result = generate_adapter("https://binance.com")
    print(result["files_written"])
    # Then reload: load_adapter("binance")
"""
from __future__ import annotations

import glob
import importlib
import importlib.util
import inspect
import os
import sys
from typing import Dict, List, Optional, Type

from adapters.base import MarketAdapter, ReadOnlyError  # noqa: F401
from adapters.polymarket_adapter import PolymarketAdapter

# ── Static registry (always available) ────────────────────────────────────────

_registry: Dict[str, Type[MarketAdapter]] = {
    "polymarket": PolymarketAdapter,
}

# ── Dynamic auto-discovery ─────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))


def _discover_adapters() -> Dict[str, Type[MarketAdapter]]:
    """
    Scan the adapters directory for *_adapter.py files and load any
    MarketAdapter subclasses found within them.

    Returns a dict mapping market_name → AdapterClass.
    """
    discovered: Dict[str, Type[MarketAdapter]] = {}

    # Ensure src/ is on the path so relative imports in adapters work
    src_dir = os.path.dirname(_HERE)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    pattern = os.path.join(_HERE, "*_adapter.py")
    for path in sorted(glob.glob(pattern)):
        module_name = os.path.splitext(os.path.basename(path))[0]  # e.g. "binance_adapter"

        # Skip already-imported modules (avoid double-loading polymarket)
        full_module = f"adapters.{module_name}"
        try:
            if full_module in sys.modules:
                mod = sys.modules[full_module]
            else:
                spec = importlib.util.spec_from_file_location(full_module, path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[full_module] = mod
                spec.loader.exec_module(mod)  # type: ignore[union-attr]

            for _name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, MarketAdapter)
                    and obj is not MarketAdapter
                    and obj.__module__ == full_module
                ):
                    key = getattr(obj, "name", module_name.replace("_adapter", ""))
                    discovered[key.lower()] = obj
        except Exception as exc:
            # Never crash the whole registry on a bad adapter file
            print(f"[adapters] Warning: could not load {path}: {exc}")

    return discovered


def _build_registry() -> None:
    """Merge dynamically discovered adapters into the registry (static wins)."""
    discovered = _discover_adapters()
    for key, cls in discovered.items():
        if key not in _registry:
            _registry[key] = cls


# Build on import
_build_registry()


# ── Public API ────────────────────────────────────────────────────────────────

def load_adapter(name: str, **kwargs) -> MarketAdapter:
    """
    Instantiate and return a registered adapter by name.

    Args:
        name:    Adapter name key, e.g. "polymarket" or "binance".
        **kwargs: Forwarded to the adapter's __init__.

    Returns:
        A ready-to-use MarketAdapter instance.

    Raises:
        KeyError: If *name* is not found in the registry.
    """
    key = name.strip().lower()
    if key not in _registry:
        # Try refreshing the registry (a new adapter file may have been written)
        _build_registry()
    if key not in _registry:
        available = ", ".join(sorted(_registry))
        raise KeyError(
            f"Unknown adapter {name!r}. Available adapters: {available}"
        )
    cls = _registry[key]
    return cls(**kwargs)


def register_adapter(name: str, cls: Type[MarketAdapter]) -> None:
    """
    Register a new adapter class under the given name.

    This allows third-party adapters to be plugged in at runtime without
    modifying the core package.

    Args:
        name: Key to register the adapter under (case-insensitive).
        cls:  A subclass of MarketAdapter.

    Raises:
        TypeError: If *cls* is not a subclass of MarketAdapter.

    Example::

        from adapters import register_adapter
        from my_pkg.kalshi_adapter import KalshiAdapter

        register_adapter("kalshi", KalshiAdapter)
    """
    if not (isinstance(cls, type) and issubclass(cls, MarketAdapter)):
        raise TypeError(f"{cls!r} must be a subclass of MarketAdapter")
    _registry[name.strip().lower()] = cls


def list_adapters() -> List[str]:
    """Return sorted list of all registered adapter names."""
    _build_registry()
    return sorted(_registry.keys())


__all__ = [
    "MarketAdapter",
    "ReadOnlyError",
    "PolymarketAdapter",
    "load_adapter",
    "register_adapter",
    "list_adapters",
]
