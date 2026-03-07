"""
risk_config.py — Global Default Risk Parameters for iEarn.Bot

These defaults apply to all positions. Individual position JSON files
may override any of these fields to customize risk per position.
"""

DEFAULT_RISK: dict = {
    # Maximum USDC allocated to a single position
    "max_position": 50,

    # Maximum total loss allowed in one calendar day (USDC)
    # Once breached, all new orders are suspended for the rest of the day
    "max_daily_loss": 30,

    # Maximum drawdown from peak value before closing (fraction, e.g. 0.35 = 35%)
    "max_drawdown": 0.35,

    # Maximum size of any single order (USDC)
    "max_order_size": 20,

    # Trailing stop: close if price falls this fraction below its peak
    # (e.g. 0.12 = close when price drops 12% from its recorded high)
    "trailing_stop": 0.12,

    # Seconds to wait before placing new orders after a stop-loss trigger
    "cooldown_period": 300,
}
