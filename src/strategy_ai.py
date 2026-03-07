"""
strategy_ai.py — AI Strategy Generator (iEarn.Bot)
===================================================
Uses SkillPay for pay-per-use billing before every AI call.

Setup:
  1. pip install requests python-dotenv openai beautifulsoup4 youtube-transcript-api pyyaml
  2. Add to .env:
       SKILLPAY_API_KEY=your_key
       SKILLPAY_USER_ID=your_telegram_id_or_wallet
       OPENROUTER_API_KEY=your_openrouter_key  (optional, for Max tier)
"""

import os
import json
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── SkillPay gate ──────────────────────────────────────────────────────────
from skillpay import charge_or_abort

def _call_proxy(messages: list, model: str = None) -> str:
    """
    Call LLM via iearn.bot proxy (no API key needed in client).
    Falls back to direct OpenRouter if user has own key.
    """
    if USE_OWN_KEY:
        # Max tier: direct call
        resp = ai_client.chat.completions.create(
            model=model or AI_MODEL,
            messages=messages,
            max_tokens=1200,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    # Pro tier: call iearn.bot proxy
    user_id = os.getenv("SKILLPAY_USER_ID", "")
    payload = {
        "messages": messages,
        "user_id": user_id,
        "model": model or AI_MODEL,
    }
    resp = requests.post(IEARN_PROXY_URL, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        if data.get("insufficient"):
            pay_url = data.get("payment_url", "https://iearn.bot/#pricing")
            print(f"❌ Insufficient balance ({data.get('balance', 0):.3f} USDT)")
            print(f"   Top up here → {pay_url}")
            raise SystemExit(1)
        raise RuntimeError(data.get("error", "Proxy error"))
    return data["content"].strip()

# ── AI client ────────────────────────────────────────────────────────────
# Priority:
#   1. iearn.bot proxy (default, no key needed, SkillPay billing)
#   2. Self-hosted OpenRouter key (Max tier)
IEARN_PROXY_URL = os.getenv("IEARN_PROXY_URL", "https://iearn.bot/api/chat")
AI_MODEL        = os.getenv("AI_MODEL", "anthropic/claude-3-haiku")

# Max tier: user brings own OpenRouter key (bypasses proxy)
_own_key = os.getenv("OPENROUTER_API_KEY", "")
if _own_key:
    try:
        import openai
        ai_client = openai.OpenAI(
            api_key=_own_key,
            base_url="https://openrouter.ai/api/v1",
        )
        USE_OWN_KEY = True
    except ImportError:
        USE_OWN_KEY = False
else:
    USE_OWN_KEY = False

USE_AI = True  # proxy is always available

STRATEGY_DIR = Path("data/strategies")
STRATEGY_DIR.mkdir(parents=True, exist_ok=True)

# ── V1 System Prompt (preserved for backward compatibility) ────────────────
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

# ── V2 System Prompt (full risk params) ───────────────────────────────────
SYSTEM_PROMPT_V2 = """You are an expert Polymarket trading strategy designer.
Analyze the provided content (article, tweet, or market insight) and any additional description,
then output a complete JSON strategy object with ALL of the following fields:

{
  "name": "V4_<short_descriptive_name>",
  "description": "Brief strategy description based on the content",
  "market_adapter": "polymarket",
  "entry": {
    "trigger": "Specific market trigger condition derived from content",
    "min_liquidity": 5000,
    "max_spread": 0.05,
    "categories": ["crypto"]
  },
  "position": {
    "side": "YES",
    "size_usdc": 10,
    "max_positions": 5,
    "max_order_size": 15,
    "max_position": 50
  },
  "exit": {
    "take_profit": 0.80,
    "stop_loss": 0.30,
    "trailing_stop": 0.10,
    "resolve_redeem": true
  },
  "risk": {
    "max_daily_loss": 25,
    "max_drawdown": 0.30,
    "cooldown_period": 300,
    "kill_switch": false
  },
  "schedule": {
    "mode": "interval",
    "every": 15,
    "unit": "minutes"
  }
}

Rules:
- Derive the trigger and strategy direction from the content/description
- Adjust risk parameters based on content sentiment and confidence level
- categories should reflect the relevant market type (crypto, politics, sports, etc.)
- Return ONLY valid JSON, no markdown, no explanation."""


# ── URL Content Fetcher ────────────────────────────────────────────────────

def _is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube link."""
    return bool(re.search(r'(youtube\.com/watch|youtu\.be/)', url))


def fetch_content(url: str) -> str:
    """
    Fetch text content from a URL.
    - YouTube URLs: tries youtube_transcript_api for subtitles
    - Other URLs: tries requests + BeautifulSoup for page text
    - On any failure: returns empty string (caller should prompt user to paste)

    Args:
        url: The URL to fetch content from

    Returns:
        Extracted text content, or empty string on failure
    """
    if _is_youtube_url(url):
        return _fetch_youtube_transcript(url)
    else:
        return _fetch_webpage_text(url)


def _fetch_youtube_transcript(url: str) -> str:
    """Fetch YouTube video transcript/subtitles."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # Extract video ID from URL
        match = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
        if not match:
            print("⚠️  Could not extract YouTube video ID from URL.")
            return ""

        video_id = match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(entry["text"] for entry in transcript_list)
        print(f"✅ YouTube transcript fetched ({len(text)} chars)")
        return text

    except ImportError:
        print("⚠️  youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
        return ""
    except Exception as e:
        print(f"⚠️  Could not fetch YouTube transcript: {e}")
        return ""


def _fetch_webpage_text(url: str) -> str:
    """Fetch and extract readable text from a webpage."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 50:
            print("⚠️  Fetched page has very little text content.")
            return ""

        print(f"✅ Page content fetched ({len(text)} chars)")
        return text[:8000]  # cap at 8k chars to avoid huge prompts

    except ImportError:
        print("⚠️  beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        return ""
    except Exception as e:
        print(f"⚠️  Could not fetch URL content: {e}")
        return ""


# ── V1 Strategy Generator (preserved, backward-compatible) ─────────────────

def generate_strategy(description: str, strategy_num: int = 4) -> dict:
    """
    Generate a trading strategy from a plain-English description.
    Charges 0.01 USDT via SkillPay before every AI call.
    If no OPENROUTER_API_KEY is set, returns a helpful notice without charging.
    """
    print(f"\n🤖 Generating strategy: \"{description}\"")

    # ── Early exit if no AI (do NOT charge) ───────────────────────────
    if not USE_AI:
        print("⚠️  AI proxy unavailable.")
        return {}

    # ── AI CALL (via iearn.bot proxy, billing handled server-side) ────
    print(f"   Model: {AI_MODEL}")
    raw = _call_proxy([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": description},
    ])

    strategy = json.loads(raw)

    # ── SAVE ───────────────────────────────────────────────────────────
    out_path = STRATEGY_DIR / f"V{strategy_num}.json"
    out_path.write_text(json.dumps(strategy, indent=2))
    print(f"✅ Strategy saved → {out_path}")
    return strategy


# ── V2 Strategy Generator (full risk params + content input) ───────────────

def generate_strategy_v2(content: str, description: str = "", strategy_num: int = 4) -> dict:
    """
    Generate a full-featured trading strategy from article/tweet content.

    Args:
        content:     Text content from a URL (article, tweet, YouTube transcript)
                     or pasted directly by the user
        description: Optional additional natural-language description or context
        strategy_num: Strategy file number suffix

    Returns:
        Strategy dict with complete risk/position/exit parameters
    """
    # Build user message combining content + description
    user_parts = []
    if content.strip():
        user_parts.append(f"[Content]\n{content[:6000]}")
    if description.strip():
        user_parts.append(f"[Additional Description]\n{description}")

    if not user_parts:
        print("⚠️  No content or description provided. Please provide text input.")
        return {}

    user_message = "\n\n".join(user_parts)
    print(f"\n🤖 Generating V2 strategy (content: {len(content)} chars, desc: {len(description)} chars)")

    # ── Early exit if no AI key (do NOT charge) ────────────────────────
    if not USE_AI:
        print(
            "⚠️  AI proxy unavailable."
        )
        return _template_strategy_v2(description or content[:100], strategy_num)

    # ── AI CALL (via iearn.bot proxy, billing handled server-side) ────
    print(f"   Model: {AI_MODEL}")
    raw = _call_proxy([
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user",   "content": user_message},
    ])

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    strategy = json.loads(raw)

    # ── SAVE JSON ──────────────────────────────────────────────────────
    out_path = STRATEGY_DIR / f"V{strategy_num}.json"
    out_path.write_text(json.dumps(strategy, indent=2))
    print(f"✅ Strategy saved → {out_path}")

    # ── SAVE params.yaml ───────────────────────────────────────────────
    from strategy_params import strategy_to_params_yaml
    yaml_str = strategy_to_params_yaml(strategy)
    yaml_path = STRATEGY_DIR / f"V{strategy_num}_params.yaml"
    yaml_path.write_text(yaml_str)
    print(f"✅ Params YAML saved → {yaml_path}")

    return strategy


def _template_strategy(description: str, num: int) -> dict:
    """Fallback template when no AI key is configured (Free tier) — V1."""
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


def _template_strategy_v2(description: str, num: int) -> dict:
    """Fallback template when no AI key is configured (Free tier) — V2."""
    s = {
        "name": f"V4_{re.sub(r'[^a-z0-9]', '_', description[:20].lower()).strip('_')}",
        "description": description,
        "market_adapter": "polymarket",
        "entry": {
            "trigger": description,
            "min_liquidity": 5000,
            "max_spread": 0.05,
            "categories": ["crypto"],
        },
        "position": {
            "side": "YES",
            "size_usdc": 10,
            "max_positions": 5,
            "max_order_size": 15,
            "max_position": 50,
        },
        "exit": {
            "take_profit": 0.80,
            "stop_loss": 0.30,
            "trailing_stop": 0.10,
            "resolve_redeem": True,
        },
        "risk": {
            "max_daily_loss": 25,
            "max_drawdown": 0.30,
            "cooldown_period": 300,
            "kill_switch": False,
        },
        "schedule": {
            "mode": "interval",
            "every": 15,
            "unit": "minutes",
        },
    }
    out_path = STRATEGY_DIR / f"V{num}.json"
    out_path.write_text(json.dumps(s, indent=2))
    print(f"✅ Template V2 strategy saved → {out_path}")

    from strategy_params import strategy_to_params_yaml
    yaml_str = strategy_to_params_yaml(s)
    yaml_path = STRATEGY_DIR / f"V{num}_params.yaml"
    yaml_path.write_text(yaml_str)
    print(f"✅ Params YAML saved → {yaml_path}")
    return s


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    """
    Usage:
      python src/strategy_ai.py generate "BTC breaks 90k, buy YES"
      python src/strategy_ai.py generate "Trump wins 2028, YES" 5
      python src/strategy_ai.py fetch "https://x.com/someone/status/123"
      python src/strategy_ai.py generate-v2 "BTC breaks 90k bullish" [--url "https://..."]
    """
    import argparse

    # Handle legacy positional usage: strategy_ai.py generate "desc" [num]
    if len(sys.argv) >= 2 and sys.argv[1] == "generate" and (
        len(sys.argv) < 3 or not sys.argv[2].startswith("--")
    ):
        desc = sys.argv[2] if len(sys.argv) > 2 else ""
        num  = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        if not desc:
            print('Usage: python src/strategy_ai.py generate "<description>" [strategy_num]')
            sys.exit(1)
        generate_strategy(desc, num)
        sys.exit(0)

    # New subcommand parser
    parser = argparse.ArgumentParser(description="iEarn.Bot Strategy AI Generator")
    subparsers = parser.add_subparsers(dest="command")

    # generate (v1, backward compat)
    p_gen = subparsers.add_parser("generate", help="Generate strategy from description (v1)")
    p_gen.add_argument("description", help="Plain-English strategy description")
    p_gen.add_argument("num", nargs="?", type=int, default=4, help="Strategy number suffix")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Fetch text content from a URL")
    p_fetch.add_argument("url", help="URL to fetch (X/Twitter post or YouTube video)")

    # generate-v2
    p_gen2 = subparsers.add_parser("generate-v2", help="Generate full strategy from content (v2)")
    p_gen2.add_argument("description", nargs="?", default="", help="Additional description")
    p_gen2.add_argument("--url", default="", help="URL to fetch content from")
    p_gen2.add_argument("--num", type=int, default=4, help="Strategy number suffix")

    args = parser.parse_args()

    if args.command == "generate":
        generate_strategy(args.description, args.num)

    elif args.command == "fetch":
        text = fetch_content(args.url)
        if text:
            print("\n── Fetched Content ──────────────────────────────────")
            print(text[:2000])
            if len(text) > 2000:
                print(f"... [{len(text) - 2000} more chars]")
        else:
            print("\n⚠️  Could not fetch content from URL.")
            print("💡 Please paste the article/tweet text manually and use:")
            print('   python src/strategy_ai.py generate-v2 "your description" --url ""')

    elif args.command == "generate-v2":
        content = ""
        if args.url:
            content = fetch_content(args.url)
            if not content:
                print("\n⚠️  Could not fetch content from the URL.")
                print("💡 Please paste the article/tweet text directly as the description argument.")
                print('   Example: python src/strategy_ai.py generate-v2 "paste your text here"')
                sys.exit(0)
        generate_strategy_v2(content, args.description, args.num)

    else:
        parser.print_help()
        sys.exit(1)
