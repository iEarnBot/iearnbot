"""
strategy_params.py — Strategy JSON → Annotated YAML Converter (iEarn.Bot)
=========================================================================
Converts a strategy dict (from generate_strategy_v2) into a human-readable,
annotated YAML string suitable for UI form rendering.

Usage:
    from strategy_params import strategy_to_params_yaml
    yaml_str = strategy_to_params_yaml(strategy_dict)
    print(yaml_str)
"""

from typing import Any


# Field-level inline comment annotations
_FIELD_COMMENTS = {
    # entry
    ("entry", "trigger"):       "触发条件描述",
    ("entry", "min_liquidity"): "最小流动性 (USDC)",
    ("entry", "max_spread"):    "最大买卖价差 (5%)",
    ("entry", "categories"):    "市场分类过滤",
    # position
    ("position", "side"):          "方向: YES 或 NO",
    ("position", "size_usdc"):     "单笔下注金额 (USDC)",
    ("position", "max_positions"): "最大同时持仓数",
    ("position", "max_order_size"):"单笔上限 (USDC)",
    ("position", "max_position"):  "单市场最大持仓 (USDC)",
    # exit
    ("exit", "take_profit"):    "止盈价格 (YES >= 0.80)",
    ("exit", "stop_loss"):      "止损价格 (YES <= 0.30)",
    ("exit", "trailing_stop"):  "追踪止损 (从高点回撤 10%)",
    ("exit", "resolve_redeem"): "到期自动赎回",
    # risk
    ("risk", "max_daily_loss"):  "当日最大亏损 (USDC)",
    ("risk", "max_drawdown"):    "最大回撤 (30%)",
    ("risk", "cooldown_period"): "止损后冷却 (秒)",
    ("risk", "kill_switch"):     "紧急熔断开关",
    # schedule
    ("schedule", "mode"):  "interval / cron / manual",
    ("schedule", "every"): "间隔数值",
    ("schedule", "unit"):  "minutes / hours / days / weeks / months",
}

# Section header comments
_SECTION_COMMENTS = {
    "name":        "策略名称",
    "description": "策略描述",
    "entry":       "入场条件",
    "position":    "仓位管理",
    "exit":        "退出条件",
    "risk":        "风控",
    "schedule":    "运行周期",
}

# Preferred section ordering
_SECTION_ORDER = [
    "name",
    "description",
    "market_adapter",
    "entry",
    "position",
    "exit",
    "risk",
    "schedule",
]


def _yaml_value(value: Any) -> str:
    """Serialize a scalar value to YAML representation."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # Quote strings that contain special chars or look like numbers/booleans
        if any(c in value for c in (':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`')) or \
           value.lower() in ("true", "false", "null", "yes", "no") or \
           (value and value[0].isdigit()):
            return f'"{value}"'
        return value
    return str(value)


def _inline_comment(section: str, key: str) -> str:
    """Return inline comment for a field, or empty string."""
    comment = _FIELD_COMMENTS.get((section, key), "")
    return f"  # {comment}" if comment else ""


def strategy_to_params_yaml(strategy: dict) -> str:
    """
    Convert a strategy dict to an annotated YAML string.

    The output includes:
    - Section header comments in Chinese
    - Inline field comments in Chinese
    - Proper YAML formatting with lists

    Args:
        strategy: Strategy dict (from generate_strategy_v2 or generate_strategy)

    Returns:
        Annotated YAML string ready for file write or UI rendering
    """
    lines = []

    # Build sorted key list: known sections first, then any extras
    known = [k for k in _SECTION_ORDER if k in strategy]
    extras = [k for k in strategy if k not in _SECTION_ORDER]
    all_keys = known + extras

    for key in all_keys:
        value = strategy[key]

        # Section header comment
        if key in _SECTION_COMMENTS:
            lines.append(f"# {_SECTION_COMMENTS[key]}")

        if isinstance(value, dict):
            lines.append(f"{key}:")
            for subkey, subval in value.items():
                comment = _inline_comment(key, subkey)
                if isinstance(subval, list):
                    lines.append(f"  {subkey}:{comment}")
                    for item in subval:
                        lines.append(f"    - {_yaml_value(item)}")
                else:
                    lines.append(f"  {subkey}: {_yaml_value(subval)}{comment}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_yaml_value(item)}")
        else:
            lines.append(f"{key}: {_yaml_value(value)}")

        lines.append("")  # blank line between sections

    return "\n".join(lines)


# ── CLI / Quick Test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys

    sample = {
        "name": "V4_btc_momentum",
        "description": "Buy YES when BTC breaks 90000",
        "market_adapter": "polymarket",
        "entry": {
            "trigger": "BTC breaks 90000",
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

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            sample = json.load(f)

    print(strategy_to_params_yaml(sample))
