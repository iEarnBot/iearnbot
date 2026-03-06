"""
strategy_ai.py — AI Strategy Generator (iEarn.Bot)
===================================================
Uses SkillPay for pay-per-use billing before every AI call.

Setup:
  1. pip install requests python-dotenv openai
  2. Add to .env:
       SKILLPAY_API_KEY=your_key
       SKILLPAY_USER_ID=your_telegram_id_or_wallet
       OPENROUTER_API_KEY=your_openrouter_key  (optional, for Max tier)
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── SkillPay gate ──────────────────────────────────────────────────────────
from skillpay import charge_or_abort

# ── AI client (OpenRouter or direct Anthropic) ────────────────────────────
try:
    import openai
    AI_BASE_URL = "https://openrouter.ai/api/v1"
    AI_MODEL    = os.getenv("AI_MODEL", "anthropic/claude-3-haiku")
    ai_client   = openai.OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url=AI_BASE_URL,
    )
    USE_AI = bool(os.getenv("OPENROUTER_API_KEY"))
except ImportError:
    USE_AI = False

STRATEGY_DIR = Path("data/strategies")
STRATEGY_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are an expert Polymarket trading strategy designer.
Given a plain-English description, output a JSON strategy object with these fields:
{
  "name": "V4_<short_name>",
  "description": "...",
  "entry": {
    "trigger": "...",          // e.g. "BTC price > 90000"
    "min_liquidity": 5000,     // USDC
    "max_spread": 0.05,        // 5%
    "categories": ["crypto"]   // Polymarket category filters
  },
  "position": {
    "side": "YES",             // YES or NO
    "size_usdc": 10,
    "max_positions": 5
  },
  "exit": {
    "take_profit": 0.75,       // sell when YES price >= 0.75
    "stop_loss": 0.30,         // sell when YES price <= 0.30
    "resolve_redeem": true
  },
  "schedule": "*/15 * * * *"  // cron: how often to scan
}
Return ONLY valid JSON, no markdown, no explanation."""


def generate_strategy(description: str, strategy_num: int = 4) -> dict:
    """
    Generate a trading strategy from a plain-English description.
    Charges 0.01 USDT via SkillPay before every AI call.
    If no OPENROUTER_API_KEY is set, returns a helpful notice without charging.
    """
    print(f"\n🤖 Generating strategy: \"{description}\"")

    # ── Early exit if no AI key (do NOT charge) ────────────────────────
    if not USE_AI:
        print(
            "⚠️  No AI key configured. Set OPENROUTER_API_KEY in .env for AI strategy generation.\n"
            "   Or use SkillPay-powered AI (coming soon)."
        )
        return {}

    # ── BILLING GATE (must pass before AI call) ────────────────────────
    charge_or_abort()   # exits with top-up link if balance < 0.01 USDT

    # ── AI CALL ────────────────────────────────────────────────────────
    print(f"   Model: {AI_MODEL}")
    resp = ai_client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": description},
        ],
        max_tokens=800,
        temperature=0.3,
    )

    raw = resp.choices[0].message.content.strip()
    strategy = json.loads(raw)

    # ── SAVE ───────────────────────────────────────────────────────────
    out_path = STRATEGY_DIR / f"V{strategy_num}.json"
    out_path.write_text(json.dumps(strategy, indent=2))
    print(f"✅ Strategy saved → {out_path}")
    return strategy


def _template_strategy(description: str, num: int) -> dict:
    """Fallback template when no AI key is configured (Free tier)."""
    s = {
        "name": f"V{num}_custom",
        "description": description,
        "entry": {
            "trigger": description,
            "min_liquidity": 3000,
            "max_spread": 0.06,
            "categories": [],
        },
        "position": {"side": "YES", "size_usdc": 10, "max_positions": 3},
        "exit": {"take_profit": 0.80, "stop_loss": 0.25, "resolve_redeem": True},
        "schedule": "*/15 * * * *",
    }
    out_path = STRATEGY_DIR / f"V{num}.json"
    out_path.write_text(json.dumps(s, indent=2))
    print(f"✅ Template strategy saved → {out_path}")
    return s


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    """
    Usage:
      python src/strategy_ai.py generate "BTC breaks 90k, buy YES"
      python src/strategy_ai.py generate "Trump wins 2028, YES" 5
    """
    if len(sys.argv) < 3 or sys.argv[1] != "generate":
        print('Usage: python src/strategy_ai.py generate "<description>" [strategy_num]')
        sys.exit(1)

    desc = sys.argv[2]
    num  = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    generate_strategy(desc, num)
