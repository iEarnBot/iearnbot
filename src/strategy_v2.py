"""
strategy_v2.py — Leaderboard Copy Strategy (Free)
Copies positions from Polymarket top traders.
"""
import logging
log = logging.getLogger("v2")

STRATEGY = {
    "name": "V2_Leaderboard_Copy",
    "description": "Mirror positions from top Polymarket traders",
    "entry": {"min_liquidity": 5000, "max_spread": 0.05, "max_price": 0.70},
    "position": {"size_usdc": 8, "max_positions": 8},
    "exit": {"take_profit": 0.82, "stop_loss": 0.28},
    "watch_addresses": [],  # Add top trader addresses here
}

def run():
    log.info("[V2] Running Leaderboard Copy strategy")
    log.info("[V2] Fetching top traders from Polymarket leaderboard...")
    # TODO: integrate with Polymarket API
    log.info("[V2] ✅ Scan complete (Polymarket API integration coming in v0.2)")
