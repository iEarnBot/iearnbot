"""
strategy_v2.py — Leaderboard Copy Strategy (Free)
Fetches top Polymarket traders from the leaderboard and inspects their positions.
v0.2: Uses real Polymarket API via polymarket.py
"""
import logging
from pathlib import Path

from dotenv import load_dotenv

import polymarket

load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────────────
Path("data/logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/logs/strategy_v2.log"),
    ],
)
log = logging.getLogger("v2")

# ── Strategy config ────────────────────────────────────────────────────────
STRATEGY = {
    "name": "V2_Leaderboard_Copy",
    "description": "Mirror positions from top Polymarket traders",
    "entry": {"min_liquidity": 5000, "max_spread": 0.05, "max_price": 0.70},
    "position": {"size_usdc": 8, "max_positions": 8},
    "exit": {"take_profit": 0.82, "stop_loss": 0.28},
    "top_traders_count": 20,   # fetch from leaderboard
    "display_top_n": 5,        # show top N in logs
}


def run():
    log.info("[V2] ═══════════════════════════════════════════════")
    log.info("[V2] Running Leaderboard Copy strategy")
    log.info("[V2] Fetching top traders from Polymarket leaderboard...")

    # ── Fetch leaderboard ──────────────────────────────────────────────────
    traders = polymarket.get_top_traders(limit=STRATEGY["top_traders_count"])

    if not traders:
        log.warning("[V2] No traders returned — check API connectivity")
        return

    log.info(f"[V2] Fetched {len(traders)} top traders")

    # ── Display top 5 ──────────────────────────────────────────────────────
    top_n = traders[:STRATEGY["display_top_n"]]
    log.info(f"[V2] Top {len(top_n)} traders on Polymarket leaderboard:")
    log.info("[V2] %-5s %-42s %12s %12s" % ("Rank", "Trader", "Profit (USDC)", "Volume (USDC)"))
    log.info("[V2] " + "-" * 75)

    for i, trader in enumerate(top_n, start=1):
        # Leaderboard fields vary — try common key names
        address = (
            trader.get("proxyWallet")
            or trader.get("address")
            or trader.get("user", "")
        )
        name = trader.get("name") or trader.get("username") or f"{address[:10]}…"
        profit  = trader.get("pnl") or trader.get("profit") or trader.get("profitLoss") or 0
        volume  = trader.get("volume") or trader.get("tradingVolume") or 0

        log.info(
            "[V2] #%-4d %-42s %12.2f %12.2f"
            % (i, name[:42], float(profit), float(volume))
        )

        # Optionally fetch that trader's open positions
        if address:
            positions = polymarket.get_positions(address)
            if positions:
                log.info(f"[V2]       ↳ {len(positions)} open position(s):")
                for pos in positions[:3]:  # show max 3 positions per trader
                    mkt   = pos.get("market") or pos.get("question", "?")
                    side  = pos.get("outcome") or pos.get("side", "?")
                    size  = pos.get("size") or pos.get("amount", 0)
                    price = pos.get("avgPrice") or pos.get("price", 0)
                    log.info(
                        f"[V2]         • {str(mkt)[:50]} | {side} | "
                        f"size={float(size):.2f} | avgPrice={float(price):.3f}"
                    )

    log.info("[V2] ✅ Leaderboard scan complete — no orders placed in v0.2")
    return traders
