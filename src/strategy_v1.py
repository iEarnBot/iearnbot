"""
strategy_v1.py — BTC Momentum Strategy (Free)
Scans and recommends BTC/crypto markets on Polymarket when entry criteria are met.
v0.2: Uses real Polymarket API via polymarket.py
"""
import logging
import os
from datetime import datetime
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
        logging.FileHandler("data/logs/strategy_v1.log"),
    ],
)
log = logging.getLogger("v1")

# ── Strategy config ────────────────────────────────────────────────────────
STRATEGY = {
    "name": "V1_BTC_Momentum",
    "description": "Buy YES on BTC/crypto markets when momentum is bullish",
    "entry": {
        "categories": ["crypto", "bitcoin"],
        "min_liquidity": 3000,   # USDC
        "max_spread":    0.07,
        "side":          "YES",
        "max_price":     0.65,   # Don't buy if already too expensive
        "min_days_left": 3,      # At least 3 days until expiry
    },
    "position": {"size_usdc": 10, "max_positions": 5},
    "exit":     {"take_profit": 0.80, "stop_loss": 0.25},
}


def run():
    log.info("[V1] ═══════════════════════════════════════════════")
    log.info("[V1] Running BTC Momentum strategy scan")
    log.info(
        f"[V1] Filters: min_liquidity={STRATEGY['entry']['min_liquidity']} USDC | "
        f"max_yes_price={STRATEGY['entry']['max_price']} | "
        f"min_days_left={STRATEGY['entry']['min_days_left']}"
    )

    # ── Fetch live markets ─────────────────────────────────────────────────
    markets = polymarket.get_markets(limit=100, active=True, category="crypto")
    log.info(f"[V1] Fetched {len(markets)} crypto markets from Polymarket")

    if not markets:
        log.warning("[V1] No markets returned — check API connectivity")
        return

    # ── Filter markets ─────────────────────────────────────────────────────
    candidates = []
    for m in markets:
        question   = m.get("question", "")
        liquidity  = polymarket.liquidity_from_market(m)
        yes_price  = polymarket.yes_price_from_market(m)
        days_left  = polymarket.days_until_expiry(m)

        if liquidity < STRATEGY["entry"]["min_liquidity"]:
            continue
        if yes_price is None or yes_price >= STRATEGY["entry"]["max_price"]:
            continue
        if days_left >= 0 and days_left < STRATEGY["entry"]["min_days_left"]:
            continue

        candidates.append({
            "question":   question,
            "liquidity":  round(liquidity, 0),
            "yes_price":  yes_price,
            "days_left":  round(days_left, 1) if days_left >= 0 else "?",
            "condition_id": m.get("conditionId", ""),
        })

    # ── Report results ─────────────────────────────────────────────────────
    log.info(f"[V1] Found {len(candidates)} candidate markets matching entry criteria:")
    if candidates:
        log.info("[V1] %-60s %8s %9s %10s" % ("Question", "Liq(USDC)", "YES Price", "Days Left"))
        log.info("[V1] " + "-" * 90)
        for c in candidates[:10]:  # print top 10
            log.info(
                "[V1] %-60s %8.0f %9.2f %10s"
                % (c["question"][:60], c["liquidity"], c["yes_price"], c["days_left"])
            )
        if len(candidates) > 10:
            log.info(f"[V1] ... and {len(candidates) - 10} more")
    else:
        log.info("[V1] No candidates found with current filters")

    log.info("[V1] ✅ Scan complete — scan only (no real orders in v0.2)")
    return candidates
