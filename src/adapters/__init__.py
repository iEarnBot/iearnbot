"""
adapters/__init__.py — Adapter registry for iEarn.Bot.

Usage
-----
    from adapters import load_adapter

    pm = load_adapter("polymarket")
    pm.smoke_test()

Extending
---------
    from adapters import register_adapter
    from my_pkg.my_adapter import MyAdapter

    register_adapter("myplatform", MyAdapter)
    adapter = load_adapter("myplatform")
"""
from __future__ import annotations

from typing import Dict, Type

from adapters.base import MarketAdapter, ReadOnlyError  # noqa: F401
from adapters.polymarket_adapter import PolymarketAdapter


# ── Registry ──────────────────────────────────────────────────────────────────

_registry: Dict[str, Type[MarketAdapter]] = {
    "polymarket": PolymarketAdapter,
}


# ── Public API ────────────────────────────────────────────────────────────────

def load_adapter(name: str, **kwargs) -> MarketAdapter:
    """
    Instantiate and return a registered adapter by name.

    Args:
        name:    Adapter name key, e.g. "polymarket".
        **kwargs: Forwarded to the adapter's __init__ (e.g. wallet_address,
                  trading_enabled).

    Returns:
        A ready-to-use MarketAdapter instance.

    Raises:
        KeyError: If *name* is not found in the registry.
    """
    key = name.strip().lower()
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


__all__ = [
    "MarketAdapter",
    "ReadOnlyError",
    "PolymarketAdapter",
    "load_adapter",
    "register_adapter",
]
