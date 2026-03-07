# Market Adapter Interface Spec

## Base Class (src/adapters/base.py)

```python
class MarketAdapter:
    name: str           # e.g. "polymarket"
    trading_enabled: bool = False  # must be True to place orders

    def get_markets(self, query="") -> list[dict]: ...
    def get_price(self, market_id: str) -> dict: ...
    # returns: {"yes_price": float, "no_price": float}

    def get_positions(self) -> list[dict]: ...
    def get_balances(self) -> dict: ...
    # returns: {"usdc": float, "native": float}

    def place_order(self, order: dict) -> dict: ...
    # raises ReadOnlyError if trading_enabled=False

    def cancel_order(self, order_id: str) -> dict: ...
    def smoke_test(self) -> bool: ...
    # read-only connectivity test, prints status
```

## Registry (src/adapters/__init__.py)
```python
from src.adapters import load_adapter, list_adapters

adapter = load_adapter("polymarket")  # returns instance
adapters = list_adapters()            # ["binance", "kalshi", "polymarket"]
```

## Generate New Adapter from URL
```python
from src.adapters.generator import generate_adapter

result = generate_adapter("https://kalshi.com")
# result = {
#   "name": "kalshi",
#   "files_written": ["src/adapters/kalshi_adapter.py", "src/adapters/kalshi_schema.json"],
#   "schema": {...},
# }
```

## Schema File Format (adapters/{name}_schema.json)
```json
{
  "name": "polymarket",
  "display_name": "Polymarket",
  "url": "https://polymarket.com",
  "auth": {"type": "private_key", "env": "POLYGON_PRIVATE_KEY"},
  "categories": ["crypto", "politics", "sports"],
  "rate_limit": {"calls_per_minute": 30},
  "trading_enabled": false,
  "status": "production"
}
```

## Supported Markets (v0.4)
| Market | Adapter | Status |
|--------|---------|--------|
| Polymarket | polymarket_adapter.py | ✅ Production |
| Binance | binance_adapter.py | 🔧 Skeleton |
| Kalshi | kalshi_adapter.py | 🔧 Skeleton |
| Any URL | generator.py | ⚡ AI-generated |
