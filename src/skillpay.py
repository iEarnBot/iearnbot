"""
skillpay.py — SkillPay Billing Integration for iEarn.Bot
=========================================================
Drop this file into your project, set SKILLPAY_API_KEY in .env, and call
`charge_or_abort(user_id)` before any AI strategy call.

ENV VARS (.env):
  SKILLPAY_API_KEY=your_key_from_dashboard
  SKILLPAY_USER_ID=your_user_id   # e.g. Telegram ID or wallet address
"""

import os
import sys
import requests
from typing import Optional

# ── Config ─────────────────────────────────────────────────────────────────
BILLING_API_URL = "https://skillpay.me"
SKILL_ID        = "524d73be-05d5-43de-8d97-57f769206eb0"
CHARGE_AMOUNT   = 0.01   # USDT per AI strategy call

def _api_key() -> str:
    key = os.getenv("SKILLPAY_API_KEY", "")
    if not key:
        raise RuntimeError("❌ SKILLPAY_API_KEY not set in .env")
    return key

def _headers() -> dict:
    return {"X-API-Key": _api_key(), "Content-Type": "application/json"}

def _user_id() -> str:
    uid = os.getenv("SKILLPAY_USER_ID", "")
    if not uid:
        raise RuntimeError("❌ SKILLPAY_USER_ID not set in .env")
    return uid

# ── ① Check balance ────────────────────────────────────────────────────────
def check_balance(user_id: Optional[str] = None) -> float:
    """Return current USDT balance for user_id."""
    uid = user_id or _user_id()
    resp = requests.get(
        f"{BILLING_API_URL}/api/v1/billing/balance",
        params={"user_id": uid},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return float(resp.json()["balance"])

# ── ② Charge per call ──────────────────────────────────────────────────────
def charge_user(user_id: Optional[str] = None, amount: float = CHARGE_AMOUNT) -> dict:
    """
    Deduct `amount` USDT for one AI call.
    Returns:
      {"ok": True,  "balance": <new_balance>}
      {"ok": False, "balance": <current>, "payment_url": "https://..."}
    """
    uid = user_id or _user_id()
    resp = requests.post(
        f"{BILLING_API_URL}/api/v1/billing/charge",
        headers=_headers(),
        json={"user_id": uid, "skill_id": SKILL_ID, "amount": amount},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("success"):
        return {"ok": True, "balance": data["balance"]}
    return {
        "ok": False,
        "balance": data.get("balance", 0),
        "payment_url": data.get("payment_url", ""),
    }

# ── ③ Generate payment link ────────────────────────────────────────────────
def get_payment_link(amount: float = 5.0, user_id: Optional[str] = None) -> str:
    """Generate a top-up link (BNB Chain USDT)."""
    uid = user_id or _user_id()
    resp = requests.post(
        f"{BILLING_API_URL}/api/v1/billing/payment-link",
        headers=_headers(),
        json={"user_id": uid, "amount": amount},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["payment_url"]

# ── ④ Gate helper (use this before every AI call) ─────────────────────────
def charge_or_abort(user_id: Optional[str] = None, amount: float = CHARGE_AMOUNT) -> None:
    """
    Call this at the top of any AI-powered function.
    Prints balance info and aborts with a top-up link if funds are insufficient.

    Usage:
        from skillpay import charge_or_abort
        charge_or_abort()
        # ... your AI call below ...
    """
    result = charge_user(user_id, amount)
    if result["ok"]:
        print(f"💳 SkillPay: charged {amount} USDT · balance: {result['balance']:.3f}")
    else:
        pay_url = result.get("payment_url") or get_payment_link(user_id=user_id)
        print(f"❌ SkillPay: insufficient balance ({result['balance']:.3f} USDT)")
        print(f"   Top up here → {pay_url}")
        sys.exit(1)


# ── CLI quick-check ────────────────────────────────────────────────────────
if __name__ == "__main__":
    """
    Quick test:
      python skillpay.py balance
      python skillpay.py charge
      python skillpay.py topup 5
    """
    from dotenv import load_dotenv
    load_dotenv()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "balance"

    if cmd == "balance":
        bal = check_balance()
        print(f"💰 Balance: {bal:.4f} USDT")

    elif cmd == "charge":
        r = charge_user()
        if r["ok"]:
            print(f"✅ Charged {CHARGE_AMOUNT} USDT · new balance: {r['balance']:.4f}")
        else:
            print(f"❌ Failed · balance: {r['balance']:.4f}")
            print(f"   Top up → {r['payment_url']}")

    elif cmd == "topup":
        amt = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        url = get_payment_link(amount=amt)
        print(f"🔗 Top-up link ({amt} USDT): {url}")

    else:
        print("Usage: python skillpay.py [balance|charge|topup <amount>]")
