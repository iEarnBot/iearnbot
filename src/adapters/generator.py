"""
generator.py — AI-powered Market Adapter Generator
用户提交市场官网 URL → 爬取文档 → AI 生成适配器骨架

Usage (CLI):
    python src/adapters/generator.py generate https://binance.com
    python src/adapters/generator.py generate https://kalshi.com

Usage (Python):
    from src.adapters.generator import generate_adapter
    result = generate_adapter("https://binance.com")
    print(result["files_written"])
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

# ── Optional deps (graceful fallback) ─────────────────────────────────────
try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    from bs4 import BeautifulSoup
    _BS4_OK = True
except ImportError:
    _BS4_OK = False

# ── Adapter output directory ───────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTERS_DIR = _HERE

# ── Well-known market schemas (template fallback when no AI available) ─────
_KNOWN_MARKETS: Dict[str, Dict[str, Any]] = {
    "binance": {
        "market_name": "binance",
        "display_name": "Binance",
        "description": "World's largest crypto exchange by trading volume.",
        "auth_type": "api_key",
        "auth_fields": ["api_key", "api_secret"],
        "base_url": "https://api.binance.com",
        "endpoints": {
            "markets":      "GET /api/v3/exchangeInfo",
            "price":        "GET /api/v3/ticker/price",
            "positions":    "GET /api/v3/account",
            "place_order":  "POST /api/v3/order",
            "cancel_order": "DELETE /api/v3/order",
        },
        "rate_limit": {"calls_per_minute": 1200},
        "trading_enabled": False,
        "notes": "Requires signed requests with HMAC-SHA256 for private endpoints.",
    },
    "kalshi": {
        "market_name": "kalshi",
        "display_name": "Kalshi",
        "description": "CFTC-regulated prediction market for event contracts.",
        "auth_type": "api_key",
        "auth_fields": ["api_key", "api_secret"],
        "base_url": "https://trading-api.kalshi.com/trade-api/v2",
        "endpoints": {
            "markets":      "GET /markets",
            "price":        "GET /markets/{ticker}",
            "positions":    "GET /portfolio/positions",
            "place_order":  "POST /portfolio/orders",
            "cancel_order": "DELETE /portfolio/orders/{order_id}",
        },
        "rate_limit": {"calls_per_minute": 60},
        "trading_enabled": False,
        "notes": "RSA key-pair or API-key auth depending on account type.",
    },
    "polymarket": {
        "market_name": "polymarket",
        "display_name": "Polymarket",
        "description": "Decentralised prediction market on Polygon.",
        "auth_type": "private_key",
        "auth_fields": ["wallet_private_key", "wallet_address"],
        "base_url": "https://clob.polymarket.com",
        "endpoints": {
            "markets":      "GET /markets",
            "price":        "GET /book?token_id={token_id}",
            "positions":    "GET /data/positions?user={address}",
            "place_order":  "POST /order",
            "cancel_order": "DELETE /order",
        },
        "rate_limit": {"calls_per_minute": 60},
        "trading_enabled": False,
        "notes": "EIP-712 signed orders; uses CLOB + Gamma API.",
    },
    "coinbase": {
        "market_name": "coinbase",
        "display_name": "Coinbase Advanced Trade",
        "description": "Coinbase Advanced Trade API (formerly Coinbase Pro).",
        "auth_type": "api_key",
        "auth_fields": ["api_key", "api_secret"],
        "base_url": "https://api.coinbase.com",
        "endpoints": {
            "markets":      "GET /api/v3/brokerage/products",
            "price":        "GET /api/v3/brokerage/products/{product_id}/ticker",
            "positions":    "GET /api/v3/brokerage/portfolios",
            "place_order":  "POST /api/v3/brokerage/orders",
            "cancel_order": "POST /api/v3/brokerage/orders/batch_cancel",
        },
        "rate_limit": {"calls_per_minute": 30},
        "trading_enabled": False,
        "notes": "JWT-based auth; uses Cloud API Keys.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Fetch market docs
# ─────────────────────────────────────────────────────────────────────────────

def fetch_market_docs(url: str) -> Dict[str, Any]:
    """
    Crawl a market's website to extract useful text for AI schema generation.

    Returns:
        {
            "name":      guessed short name (e.g. "binance"),
            "home_text": text from homepage,
            "api_text":  concatenated text from API/docs pages,
            "api_urls":  list of discovered API/docs URLs,
        }
    Fetch failures are silenced — callers receive empty strings.
    """
    result: Dict[str, Any] = {
        "name": "",
        "home_text": "",
        "api_text": "",
        "api_urls": [],
    }

    if not _REQUESTS_OK or not _BS4_OK:
        print("[generator] Warning: requests/beautifulsoup4 not available — skipping crawl.", file=sys.stderr)
        return result

    parsed = urlparse(url if url.startswith("http") else "https://" + url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Guess name from domain
    domain = parsed.netloc.lstrip("www.").split(".")[0]
    result["name"] = domain.lower()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; iEarnBot/0.4; +https://iearn.bot)"
        )
    }

    def _fetch_text(fetch_url: str) -> str:
        try:
            resp = requests.get(fetch_url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove script/style noise
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:8000]
        except Exception as exc:
            print(f"[generator] Fetch failed for {fetch_url}: {exc}", file=sys.stderr)
            return ""

    def _find_api_links(fetch_url: str) -> List[str]:
        """Discover API / docs links on a page."""
        try:
            resp = requests.get(fetch_url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            links: List[str] = []
            keywords = re.compile(r"(api|docs|developer|documentation|reference)", re.I)
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                text: str = a.get_text(strip=True)
                if keywords.search(href) or keywords.search(text):
                    full = urljoin(base_url, href) if not href.startswith("http") else href
                    if urlparse(full).netloc in (parsed.netloc, ""):
                        links.append(full)
            # Deduplicate while preserving order
            seen: set = set()
            return [l for l in links if not (l in seen or seen.add(l))]
        except Exception as exc:
            print(f"[generator] Link discovery failed for {fetch_url}: {exc}", file=sys.stderr)
            return []

    print(f"[generator] Fetching homepage: {url}", file=sys.stderr)
    result["home_text"] = _fetch_text(url)

    api_links = _find_api_links(url)
    # Limit to 3 most relevant pages
    api_links = api_links[:3]
    result["api_urls"] = api_links

    api_texts: List[str] = []
    for link in api_links:
        print(f"[generator] Fetching API doc: {link}", file=sys.stderr)
        api_texts.append(_fetch_text(link))

    result["api_text"] = "\n\n".join(api_texts)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — AI schema generation
# ─────────────────────────────────────────────────────────────────────────────

_AI_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert trading API integration engineer.
    Given documentation about a trading platform, generate a Python adapter class.

    Output a JSON object with these fields:
    {
      "market_name": "binance",
      "display_name": "Binance",
      "description": "...",
      "auth_type": "api_key",
      "auth_fields": ["api_key", "api_secret"],
      "base_url": "https://api.binance.com",
      "endpoints": {
        "markets":      "GET /api/v3/exchangeInfo",
        "price":        "GET /api/v3/ticker/price",
        "positions":    "GET /api/v3/account",
        "place_order":  "POST /api/v3/order",
        "cancel_order": "DELETE /api/v3/order"
      },
      "rate_limit": {"calls_per_minute": 60},
      "trading_enabled": false,
      "notes": "..."
    }
    Return ONLY valid JSON, no markdown fences, no commentary.
""")


def _call_ai(docs: Dict[str, Any], ai_client=None) -> Optional[Dict[str, Any]]:
    """
    Ask AI to generate an adapter schema from crawled docs.
    Returns parsed dict on success, None on failure.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key and ai_client is None:
        return None  # Fall through to template mode

    user_msg = (
        f"Market homepage: {docs.get('name', 'unknown')}\n\n"
        f"--- Homepage text (first 4000 chars) ---\n{docs.get('home_text', '')[:4000]}\n\n"
        f"--- API docs text (first 4000 chars) ---\n{docs.get('api_text', '')[:4000]}"
    )

    # Use provided ai_client, or build one from OPENROUTER_API_KEY
    try:
        if ai_client is not None:
            raw = ai_client(system=_AI_SYSTEM_PROMPT, user=user_msg)
        else:
            # Direct OpenRouter HTTP call
            import requests as _req
            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": _AI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.2,
                "max_tokens": 1000,
            }
            resp = _req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?\n?", "", str(raw)).strip().rstrip("`")
        return json.loads(raw)
    except Exception as exc:
        print(f"[generator] AI call failed: {exc}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — File generation
# ─────────────────────────────────────────────────────────────────────────────

def _build_schema_from_docs(docs: Dict[str, Any], market_url: str) -> Dict[str, Any]:
    """
    Build a best-effort schema using only crawled text (no AI).
    Checks well-known markets first, then produces a generic skeleton.
    """
    name = docs.get("name", "unknown").lower()

    # Check well-known market database
    if name in _KNOWN_MARKETS:
        schema = dict(_KNOWN_MARKETS[name])
        print(f"[generator] Using built-in schema for known market: {name}", file=sys.stderr)
        return schema

    # Generic fallback
    display = name.title()
    return {
        "market_name": name,
        "display_name": display,
        "description": f"{display} trading platform.",
        "auth_type": "api_key",
        "auth_fields": ["api_key", "api_secret"],
        "base_url": market_url.rstrip("/"),
        "endpoints": {
            "markets":      "GET /api/markets",
            "price":        "GET /api/price/{market_id}",
            "positions":    "GET /api/positions",
            "place_order":  "POST /api/orders",
            "cancel_order": "DELETE /api/orders/{order_id}",
        },
        "rate_limit": {"calls_per_minute": 60},
        "trading_enabled": False,
        "notes": "Auto-generated skeleton — fill in real endpoints.",
    }


def _render_adapter_code(schema: Dict[str, Any]) -> str:
    """Render the Python adapter class from a schema dict."""
    mname = schema["market_name"]          # e.g. "binance"
    dname = schema["display_name"]          # e.g. "Binance"
    cname = mname.title().replace("_", "").replace("-", "") + "Adapter"  # e.g. "BinanceAdapter"
    env_prefix = mname.upper().replace("-", "_")  # e.g. "BINANCE"
    base_url = schema.get("base_url", "https://api.example.com")
    endpoints = schema.get("endpoints", {})
    trading = schema.get("trading_enabled", False)

    ep_comments = "\n".join(
        f"        #   {k}: {v}" for k, v in endpoints.items()
    )

    code = f'''\
"""
{dname} Adapter — auto-generated by iEarn.Bot generator.py
Do NOT commit credentials. Set environment variables instead.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

# Allow running as __main__ from repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from adapters.base import MarketAdapter, ReadOnlyError  # noqa: F401

load_dotenv()


class {cname}(MarketAdapter):
    """
    {dname} market adapter (auto-generated skeleton).

    Endpoints:
{ep_comments}
    """

    name = "{mname}"
    trading_enabled = {trading}

    def __init__(self, trading_enabled: bool = {trading}) -> None:
        self.trading_enabled = trading_enabled
        self.api_key    = os.getenv("{env_prefix}_API_KEY", "")
        self.api_secret = os.getenv("{env_prefix}_API_SECRET", "")
        self.base_url   = "{base_url}"
        self.session    = requests.Session()
        self.session.headers.update({{"Content-Type": "application/json"}})

    # ── Markets ─────────────────────────────────────────────────────────────

    def get_markets(self, query: str = "") -> List[Dict[str, Any]]:
        # TODO: implement using {endpoints.get("markets", "GET /api/markets")}
        return []

    # ── Prices ───────────────────────────────────────────────────────────────

    def get_price(self, market_id: str) -> Dict[str, float]:
        # TODO: implement using {endpoints.get("price", "GET /api/price")}
        return {{}}

    # ── Portfolio ─────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Dict[str, Any]]:
        # TODO: implement using {endpoints.get("positions", "GET /api/positions")}
        return []

    def get_balances(self) -> Dict[str, float]:
        # TODO: fetch from account endpoint
        return {{"usdc": 0.0, "native": 0.0}}

    # ── Trading ──────────────────────────────────────────────────────────────

    def _place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: implement using {endpoints.get("place_order", "POST /api/orders")}
        return {{}}

    def _cancel_order(self, order_id: str) -> Dict[str, Any]:
        # TODO: implement using {endpoints.get("cancel_order", "DELETE /api/orders")}
        return {{}}

    # ── Health ───────────────────────────────────────────────────────────────

    def smoke_test(self) -> bool:
        print(f"[{dname}] Smoke test...")
        try:
            balances = self.get_balances()
            print(f"[{dname}] Balances: {{balances}}")
            markets = self.get_markets()
            print(f"[{dname}] Markets fetched: {{len(markets)}}")
            print(f"[{dname}] Smoke test PASSED (skeleton — no live calls yet)")
            return True
        except Exception as exc:
            print(f"[{dname}] Smoke test FAILED: {{exc}}")
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        adapter = {cname}()
        adapter.smoke_test()
'''
    return code


def _render_schema_json(schema: Dict[str, Any], market_url: str) -> Dict[str, Any]:
    """Build the JSON schema file content."""
    return {
        "name":          schema["market_name"],
        "display_name":  schema["display_name"],
        "description":   schema.get("description", ""),
        "url":           market_url,
        "auth": {
            "type":   schema.get("auth_type", "api_key"),
            "fields": schema.get("auth_fields", []),
        },
        "endpoints":      schema.get("endpoints", {}),
        "rate_limit":     schema.get("rate_limit", {"calls_per_minute": 60}),
        "trading_enabled": schema.get("trading_enabled", False),
        "generated_at":  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "status":        "skeleton",
        "notes":         schema.get("notes", ""),
    }


def _write_adapter_files(schema: Dict[str, Any], market_url: str) -> List[str]:
    """Write adapter .py and _schema.json to the adapters directory."""
    mname = schema["market_name"]
    files_written: List[str] = []

    # Python adapter
    adapter_path = os.path.join(_ADAPTERS_DIR, f"{mname}_adapter.py")
    with open(adapter_path, "w", encoding="utf-8") as f:
        f.write(_render_adapter_code(schema))
    files_written.append(adapter_path)
    print(f"[generator] Wrote: {adapter_path}", file=sys.stderr)

    # JSON schema
    schema_path = os.path.join(_ADAPTERS_DIR, f"{mname}_schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(_render_schema_json(schema, market_url), f, indent=2)
    files_written.append(schema_path)
    print(f"[generator] Wrote: {schema_path}", file=sys.stderr)

    return files_written


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_adapter(market_url: str, ai_client=None) -> Dict[str, Any]:
    """
    From a market homepage URL, generate a full adapter skeleton.

    Returns:
        {
            "name":           "binance",
            "schema":         {...},          # schema dict used
            "adapter_code":   "...",          # rendered Python source
            "files_written":  ["/path/a.py", "/path/a_schema.json"],
            "mode":           "ai" | "known" | "template",
        }
    """
    url = market_url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    # Step 1: Crawl
    print(f"[generator] Crawling: {url}", file=sys.stderr)
    docs = fetch_market_docs(url)

    # Step 2: Schema — try AI, then known market db, then generic template
    schema: Optional[Dict[str, Any]] = None
    mode = "template"

    schema = _call_ai(docs, ai_client)
    if schema:
        mode = "ai"
        print(f"[generator] AI mode — schema generated for: {schema.get('market_name')}", file=sys.stderr)
    else:
        schema = _build_schema_from_docs(docs, url)
        mode = "known" if docs.get("name", "") in _KNOWN_MARKETS else "template"
        print(f"[generator] Template mode ({mode}) — schema: {schema.get('market_name')}", file=sys.stderr)

    # Step 3: Write files
    files_written = _write_adapter_files(schema, url)

    adapter_code = _render_adapter_code(schema)

    return {
        "name":          schema["market_name"],
        "schema":        schema,
        "adapter_code":  adapter_code,
        "files_written": files_written,
        "mode":          mode,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _cli() -> None:
    """
    CLI entry point.
    Usage:
        python generator.py generate <url>
        python generator.py generate https://binance.com
    """
    if len(sys.argv) < 3 or sys.argv[1] != "generate":
        print("Usage: python generator.py generate <market_url>", file=sys.stderr)
        sys.exit(1)

    market_url = sys.argv[2]
    print(f"\n=== iEarn.Bot Adapter Generator ===")
    print(f"Target: {market_url}\n")

    result = generate_adapter(market_url)

    print(f"\n✅ Generated adapter: {result['name']}")
    print(f"   Mode:  {result['mode']}")
    print(f"   Files:")
    for f in result["files_written"]:
        print(f"     {f}")

    # Quick import validation
    mname = result["name"]
    adapter_file = os.path.join(_ADAPTERS_DIR, f"{mname}_adapter.py")
    if os.path.exists(adapter_file):
        print(f"\n   Run smoke test:")
        print(f"     python {adapter_file} smoke")


if __name__ == "__main__":
    _cli()
