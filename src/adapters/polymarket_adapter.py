"""
adapters/polymarket_adapter.py — Polymarket adapter for iEarn.Bot.

Wraps the functions in src/polymarket.py behind the MarketAdapter interface.
All API calls are read-only by default (trading_enabled=False).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List

# Allow running as __main__ from repo root: python src/adapters/polymarket_adapter.py smoke
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import polymarket as _pm          # src/polymarket.py — never modified
from adapters.base import MarketAdapter, ReadOnlyError  # noqa: F401 (re-exported)

log = logging.getLogger("adapters.polymarket")


class PolymarketAdapter(MarketAdapter):
    """
    Polymarket market adapter.

    Delegates all data-fetching to the functions already implemented in
    src/polymarket.py.  No code is duplicated; the original file is never
    touched.

    Args:
        wallet_address:  EVM wallet address (0x…) used for position/balance
                         lookups.  Can also be supplied via the environment
                         variable POLYGON_WALLET_ADDRESS.
        trading_enabled: Set to True to allow place_order / cancel_order.
                         Defaults to False (read-only / paper-trading mode).
        default_limit:   Default number of markets to fetch in get_markets().
    """

    trading_enabled: bool = False

    def __init__(
        self,
        wallet_address: str = "",
        trading_enabled: bool = False,
        default_limit: int = 50,
    ) -> None:
        self.wallet_address  = wallet_address or os.environ.get("POLYGON_WALLET_ADDRESS", "")
        self.trading_enabled = trading_enabled
        self.default_limit   = default_limit

    # ── Markets ──────────────────────────────────────────────────────────────

    def get_markets(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Fetch active Polymarket markets.

        Args:
            query: Optional category string (e.g. "crypto", "politics").
                   Passed to polymarket.get_markets(category=query).

        Returns:
            List of market dicts from the Gamma API.
        """
        category = query if query else None
        markets  = _pm.get_markets(limit=self.default_limit, active=True, category=category)
        log.debug(f"[PolymarketAdapter] get_markets(query={query!r}): {len(markets)} results")
        return markets

    # ── Prices ───────────────────────────────────────────────────────────────

    def get_price(self, market_id: str) -> Dict[str, float]:
        """
        Fetch YES/NO prices for a market by its conditionId.

        Args:
            market_id: The market's conditionId (hex string).

        Returns:
            {"yes_price": float, "no_price": float} plus additional CLOB keys.
        """
        price_data = _pm.get_market_price(market_id)
        result: Dict[str, float] = {
            "yes_price": price_data.get("yes_price") or 0.0,
            "no_price":  price_data.get("no_price")  or 0.0,
        }
        # Surface extra keys (spread, condition_id) if present
        result.update({k: v for k, v in price_data.items() if k not in result})
        return result

    # ── Portfolio ─────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Return open positions for self.wallet_address.

        Returns:
            List of position dicts from the Gamma API.
            Empty list if no wallet address is configured.
        """
        if not self.wallet_address:
            log.warning("[PolymarketAdapter] get_positions: wallet_address not set")
            return []
        return _pm.get_positions(self.wallet_address)

    def get_balances(self) -> Dict[str, float]:
        """
        Return on-chain balances for self.wallet_address.

        Polymarket's public API does not expose a dedicated balance endpoint;
        this method estimates USDC exposure from open positions and returns
        a best-effort dict.  For accurate on-chain balances you would query
        the Polygon RPC directly (requires web3.py — out of scope here).

        Returns:
            {"usdc": float, "native": float}
        """
        # Best-effort: sum size*avgPrice across open positions as "deployed USDC"
        usdc   = 0.0
        native = 0.0  # MATIC balance not available without on-chain RPC

        positions = self.get_positions()
        for pos in positions:
            size      = float(pos.get("size", pos.get("amount", 0)) or 0)
            avg_price = float(pos.get("avgPrice", pos.get("average_price", 0)) or 0)
            usdc += size * avg_price

        log.debug(f"[PolymarketAdapter] get_balances: deployed_usdc={usdc:.2f}")
        return {"usdc": round(usdc, 4), "native": native}

    # ── Trading (read-only guard inherited from base) ─────────────────────────

    def _place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Live order placement stub.

        Full implementation would use the Polymarket CLOB signing flow
        (py-clob-client).  Until that is integrated this raises
        NotImplementedError so callers know it is not yet wired up.
        """
        raise NotImplementedError(
            "Live order placement is not yet implemented for PolymarketAdapter. "
            "Integrate py-clob-client and override _place_order()."
        )

    def _cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Live order cancellation stub — see _place_order note."""
        raise NotImplementedError(
            "Live order cancellation is not yet implemented for PolymarketAdapter."
        )

    # ── Health ────────────────────────────────────────────────────────────────

    def smoke_test(self) -> bool:
        """
        Read-only connectivity test.

        Fetches a small market sample and (if wallet configured) positions,
        then prints a summary.  Never places orders.

        Returns:
            True if API is reachable, False on any exception.
        """
        try:
            print("[PolymarketAdapter] smoke_test — starting …")

            # Markets
            markets = _pm.get_markets(limit=5, active=True)
            print(f"  ✓ markets reachable  — sample size: {len(markets)}")

            # Balances (best-effort)
            balances = self.get_balances()
            print(f"  ✓ balances           — usdc={balances['usdc']:.4f}  native={balances['native']:.4f}")

            # Positions
            if self.wallet_address:
                positions = self.get_positions()
                print(f"  ✓ positions          — {len(positions)} open")
            else:
                print("  ⚠ positions          — skipped (no wallet_address configured)")

            print(f"  trading_enabled      = {self.trading_enabled}")
            print("[PolymarketAdapter] smoke_test PASSED ✓")
            return True
        except Exception as exc:
            print(f"[PolymarketAdapter] smoke_test FAILED ✗ — {exc}")
            log.exception("[PolymarketAdapter] smoke_test exception")
            return False


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PolymarketAdapter CLI",
        epilog="Example: python src/adapters/polymarket_adapter.py smoke",
    )
    parser.add_argument(
        "command",
        choices=["smoke"],
        help="Command to run.  Currently only 'smoke' (connectivity test) is supported.",
    )
    parser.add_argument(
        "--wallet",
        default=os.environ.get("POLYGON_WALLET_ADDRESS", ""),
        help="EVM wallet address for position/balance lookups (or set POLYGON_WALLET_ADDRESS).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s  %(name)s  %(message)s",
    )

    adapter = PolymarketAdapter(wallet_address=args.wallet)

    if args.command == "smoke":
        ok = adapter.smoke_test()
        sys.exit(0 if ok else 1)
