# Risk Parameter Reference

## Per-Position Risk Fields (in position JSON or params.yaml)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stop_loss` | float | 0.30 | Exit when price ≤ this value |
| `take_profit` | float | 0.80 | Exit when price ≥ this value |
| `trailing_stop` | float | 0.12 | Exit when price drops X% from peak |
| `max_position` | float | 50 | Max USDC in single market |
| `max_daily_loss` | float | 30 | Max USDC loss per day (halts trading) |
| `max_drawdown` | float | 0.35 | Max % drawdown from peak balance |
| `max_order_size` | float | 20 | Max USDC per single order |
| `cooldown_period` | int | 300 | Seconds to pause after stop-loss trigger |
| `kill_switch` | bool | false | If true, close position immediately |

## Global Defaults (src/risk_config.py)
```python
DEFAULT_RISK = {
    "max_position": 50,
    "max_daily_loss": 30,
    "max_drawdown": 0.35,
    "max_order_size": 20,
    "trailing_stop": 0.12,
    "cooldown_period": 300,
}
```
Per-position fields override global defaults.

## Kill-Switch
- File: `data/risk/kill_switch.flag`
- Create: `python src/risk.py kill`
- Remove: `python src/risk.py resume`
- Effect: All strategy jobs skip execution while flag exists

## Daily Loss Tracking
- File: `data/risk/daily_loss.json`
- Resets at midnight (date check)
- When `loss_usdc >= max_daily_loss`: new orders blocked for the day

## Audit Trail
- File: `data/risk/closed_positions.jsonl`
- Every close recorded: timestamp, reason, exit_price, pnl
