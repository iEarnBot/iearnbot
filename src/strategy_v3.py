"""
strategy_v3.py — Wallet Tracking Strategy (Free)
Tracks and copies specific wallet addresses.
"""
import os, logging
from dotenv import load_dotenv
load_dotenv()
log = logging.getLogger("v3")

# Add wallet addresses to track in .env as TRACK_WALLETS=0x...,0x...
WATCH_WALLETS = [w.strip() for w in os.getenv("TRACK_WALLETS", "").split(",") if w.strip()]

def run():
    log.info("[V3] Running Wallet Tracking strategy")
    if not WATCH_WALLETS:
        log.warning("[V3] No wallets configured. Set TRACK_WALLETS=0x... in .env")
        return
    log.info(f"[V3] Tracking {len(WATCH_WALLETS)} wallet(s)")
    # TODO: integrate with Polymarket API
    log.info("[V3] ✅ Scan complete (Polymarket API integration coming in v0.2)")
