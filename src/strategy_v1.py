"""
strategy_v1.py — BTC Momentum Strategy (Free)
Buys YES on BTC-related markets when price signal is bullish.
"""
import os, logging
from dotenv import load_dotenv
load_dotenv()
log = logging.getLogger("v1")

STRATEGY = {
    "name": "V1_BTC_Momentum",
    "description": "Buy YES on BTC markets when momentum is bullish",
    "entry": {
        "categories": ["crypto", "bitcoin"],
        "min_liquidity": 3000,
        "max_spread": 0.07,
        "side": "YES",
        "max_price": 0.65,   # Don't buy if already too expensive
    },
    "position": {"size_usdc": 10, "max_positions": 5},
    "exit": {"take_profit": 0.80, "stop_loss": 0.25},
}

def run():
    log.info(f"[V1] Running BTC Momentum strategy")
    log.info(f"[V1] Looking for BTC markets | min_liquidity={STRATEGY['entry']['min_liquidity']}")
    # TODO: integrate with Polymarket API to scan markets + execute
    log.info(f"[V1] ✅ Scan complete (Polymarket API integration coming in v0.2)")
