"""
polymarket.py — Polymarket API Client
Fetches live markets, prices, and positions from Polymarket CLOB API.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

log = logging.getLogger("polymarket")

CLOB_API  = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

_SESSION = requests.Session()
_SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "iEarn.Bot/0.2",
})


# ── Markets ────────────────────────────────────────────────────────────────

def get_markets(
    limit: int = 50,
    active: bool = True,
    category: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch active markets from Polymarket Gamma API.

    Args:
        limit:    Max number of markets to return.
        active:   If True, filter to only active / open markets.
        category: Optional tag/category string (e.g. "crypto", "politics").

    Returns:
        List of market dicts with keys: id, question, conditionId,
        volume, liquidity, endDate, outcomePrices, etc.
    """
    params: Dict = {"limit": limit}
    if active:
        params["active"] = "true"
        params["closed"] = "false"
    if category:
        params["tag"] = category

    try:
        resp = _SESSION.get(f"{GAMMA_API}/markets", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Gamma API returns either a list or {"markets": [...]}
        markets = data if isinstance(data, list) else data.get("markets", [])
        log.info(f"[polymarket] get_markets: fetched {len(markets)} markets (category={category})")
        return markets
    except requests.RequestException as exc:
        log.error(f"[polymarket] get_markets failed: {exc}")
        return []


# ── Prices ─────────────────────────────────────────────────────────────────

def get_market_price(condition_id: str) -> Dict:
    """
    Get current best YES/NO prices for a market from the CLOB.

    Args:
        condition_id: The market's conditionId (hex string).

    Returns:
        Dict with keys: yes_price, no_price, spread, condition_id.
        Returns empty dict on error.
    """
    try:
        # CLOB /price endpoint: GET /price?token_id=<yes_token_id>
        # We first need the token IDs from the market data; fall back to
        # the simpler /book endpoint for a quick mid-price estimate.
        resp = _SESSION.get(
            f"{CLOB_API}/markets/{condition_id}",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        tokens = data.get("tokens", [])
        yes_price = no_price = None
        for tok in tokens:
            outcome = (tok.get("outcome") or "").upper()
            price   = float(tok.get("price", 0))
            if outcome == "YES":
                yes_price = price
            elif outcome == "NO":
                no_price = price

        if yes_price is None and no_price is not None:
            yes_price = round(1.0 - no_price, 4)
        if no_price is None and yes_price is not None:
            no_price = round(1.0 - yes_price, 4)

        spread = round(abs((yes_price or 0) + (no_price or 0) - 1.0), 4)
        return {
            "condition_id": condition_id,
            "yes_price":    yes_price,
            "no_price":     no_price,
            "spread":       spread,
        }
    except requests.RequestException as exc:
        log.error(f"[polymarket] get_market_price({condition_id}) failed: {exc}")
        return {}


# ── Positions ──────────────────────────────────────────────────────────────

def get_positions(wallet_address: str) -> List[Dict]:
    """
    Get open positions for a wallet via the Polymarket portfolio API.

    Args:
        wallet_address: EVM wallet address (0x…).

    Returns:
        List of position dicts with keys: market, outcome, size, avgPrice, pnl.
    """
    if not wallet_address:
        log.warning("[polymarket] get_positions: no wallet_address provided")
        return []
    try:
        resp = _SESSION.get(
            f"{GAMMA_API}/positions",
            params={"user": wallet_address.lower()},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        positions = data if isinstance(data, list) else data.get("positions", [])
        log.info(
            f"[polymarket] get_positions({wallet_address[:8]}…): "
            f"{len(positions)} open positions"
        )
        return positions
    except requests.RequestException as exc:
        log.error(f"[polymarket] get_positions failed: {exc}")
        return []


# ── Leaderboard ────────────────────────────────────────────────────────────

def get_top_traders(limit: int = 20) -> List[Dict]:
    """
    Fetch the Polymarket leaderboard (top traders by profit).

    Args:
        limit: Number of traders to return.

    Returns:
        List of trader dicts with keys: name/address, profit, volume, rank.
    """
    try:
        resp = _SESSION.get(
            f"{GAMMA_API}/leaderboard",
            params={"limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        traders = data if isinstance(data, list) else data.get("data", data.get("leaderboard", []))
        log.info(f"[polymarket] get_top_traders: {len(traders)} traders fetched")
        return traders[:limit]
    except requests.RequestException as exc:
        log.error(f"[polymarket] get_top_traders failed: {exc}")
        return []


# ── Helpers ────────────────────────────────────────────────────────────────

def days_until_expiry(market: Dict) -> float:
    """Return days remaining until market end date (float). -1 if unknown."""
    end_raw = market.get("endDate") or market.get("end_date_iso") or ""
    if not end_raw:
        return -1.0
    try:
        # endDate may be "2025-06-01T00:00:00Z" or epoch ms
        if isinstance(end_raw, (int, float)):
            end_dt = datetime.fromtimestamp(end_raw / 1000, tz=timezone.utc)
        else:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        delta = end_dt - datetime.now(tz=timezone.utc)
        return delta.total_seconds() / 86400
    except Exception:
        return -1.0


def yes_price_from_market(market: Dict) -> Optional[float]:
    """Extract YES price from Gamma market dict (outcomePrices field)."""
    prices = market.get("outcomePrices")
    if isinstance(prices, list) and len(prices) >= 1:
        try:
            return float(prices[0])
        except (ValueError, TypeError):
            pass
    return None


def liquidity_from_market(market: Dict) -> float:
    """Extract liquidity (USDC) from Gamma market dict."""
    for key in ("liquidity", "liquidityNum", "volume"):
        val = market.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return 0.0
