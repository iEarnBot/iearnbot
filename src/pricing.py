PRICING_TIERS = {
    "mini": {
        "name": "Mini",
        "price_usd": 9.9,
        "billing": "per_strategy",
        "max_strategies": 1,
        "ai_modifications": 3,
        "description": "单次付费，策略本地运行永久免费",
        "features": [
            "1个策略部署",
            "免费修改3次",
            "本地运行永久免费",
            "基础风控套件"
        ]
    },
    "pro": {
        "name": "Pro",
        "price_usd": 19.0,
        "billing": "monthly",
        "max_strategies": 10,
        "ai_modifications": 6,
        "description": "包月，10个策略，每个可免费修改6次",
        "features": [
            "10个策略部署/月",
            "每策略免费修改6次",
            "本地运行永久免费",
            "完整风控套件",
            "优先支持"
        ]
    },
    "max": {
        "name": "Max",
        "price_usd": 19.9,
        "billing": "yearly",
        "max_strategies": -1,  # unlimited
        "ai_modifications": -1,  # unlimited
        "description": "包年，无限策略，自带LLM-API",
        "features": [
            "无限策略部署",
            "每策略无限次修改",
            "本地运行永久免费",
            "自接LLM-API（节省成本）",
            "完整风控套件",
            "优先支持 + 早期功能"
        ]
    }
}
