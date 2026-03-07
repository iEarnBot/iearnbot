"""
adapters/base.py — Abstract base class for market adapters.

All exchange/prediction-market integrations must subclass MarketAdapter
and implement every method defined here. This ensures a uniform interface
regardless of the underlying platform (Polymarket, Manifold, Kalshi, …).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


# ── Exceptions ─────────────────────────────────────────────────────────────

class ReadOnlyError(Exception):
    """
    Raised when a write operation (place_order, cancel_order) is attempted
    on an adapter that has trading_enabled=False (read-only / paper mode).
    """
    def __init__(self, message: str = "Trading is disabled. Set trading_enabled=True to place orders."):
        super().__init__(message)


# ── Base Adapter ────────────────────────────────────────────────────────────

class MarketAdapter(ABC):
    """
    Abstract base class for all iEarn.Bot market adapters.

    Subclasses must implement every abstract method. The optional
    `trading_enabled` flag gates write operations; adapters that do not
    support live trading may leave it as False permanently.

    Attributes:
        trading_enabled: When False (default), place_order and cancel_order
                         raise ReadOnlyError instead of executing.
    """

    trading_enabled: bool = False

    # ── Markets ─────────────────────────────────────────────────────────────

    @abstractmethod
    def get_markets(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Fetch available markets, optionally filtered by a search query.

        Args:
            query: Free-text search / category filter (adapter-specific).

        Returns:
            List of market dicts. Keys may vary by adapter but should
            include at minimum: id, question/title.
        """

    # ── Prices ──────────────────────────────────────────────────────────────

    @abstractmethod
    def get_price(self, market_id: str) -> Dict[str, float]:
        """
        Fetch the current YES/NO price for a binary market.

        Args:
            market_id: Platform-specific market identifier.

        Returns:
            Dict with keys:
                yes_price (float): Probability / price for the YES outcome.
                no_price  (float): Probability / price for the NO outcome.
            May include additional keys (spread, timestamp, …).
        """

    # ── Portfolio ────────────────────────────────────────────────────────────

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Return all open positions for the authenticated account.

        Returns:
            List of position dicts. Keys should include at minimum:
            market_id, outcome, size, avg_price.
        """

    @abstractmethod
    def get_balances(self) -> Dict[str, float]:
        """
        Return current account balances.

        Returns:
            Dict with keys:
                usdc   (float): USDC / stable-coin balance.
                native (float): Native token balance (MATIC, ETH, …).
            May include additional keys.
        """

    # ── Trading ──────────────────────────────────────────────────────────────

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a new order.

        Raises ReadOnlyError unless trading_enabled is True.

        Args:
            order: Order specification dict (keys are adapter-specific).

        Returns:
            Order confirmation dict.
        """
        if not self.trading_enabled:
            raise ReadOnlyError()
        return self._place_order(order)

    def _place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal implementation hook for place_order.
        Subclasses that support live trading should override this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement live order placement.")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.

        Raises ReadOnlyError unless trading_enabled is True.

        Args:
            order_id: Platform-specific order identifier.

        Returns:
            Cancellation confirmation dict.
        """
        if not self.trading_enabled:
            raise ReadOnlyError()
        return self._cancel_order(order_id)

    def _cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Internal implementation hook for cancel_order.
        Subclasses that support live trading should override this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement live order cancellation.")

    # ── Health ───────────────────────────────────────────────────────────────

    @abstractmethod
    def smoke_test(self) -> bool:
        """
        Read-only connectivity test. Should:
          1. Fetch balances and print them.
          2. Fetch a small sample of markets and print the count.
          3. Return True if both calls succeed without raising.

        This must never place orders or modify state.

        Returns:
            True if the adapter can reach the market API, False otherwise.
        """
