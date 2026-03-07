# Polymarket 本地机器人架构文档

## 文件结构
```
~/.openclaw/workspace/
├── polymarket_bot.py          # 主交易循环（三策略）
├── polymarket_take_profit.py  # 止盈引擎（独立可单独运行）
├── polymarket_bot.log         # 运行日志
├── polymarket_leaderboard/    # 每日榜单存档
│   └── YYYY-MM-DD.json
├── polymarket_v3sg_accounts.json  # V3-SG 目标账号名单
└── polymarket_rename_followed.json # rename 已跟单记录

~/.openclaw/skills/polyclaw/
├── scripts/trade.py           # 买入引擎（split+CLOB）
├── lib/clob_client.py         # CLOB卖出接口
└── .env                       # 私钥配置
```

## 运行方式

### 手动执行
```bash
cd ~/.openclaw/workspace

# 单次执行（生产）
python3 polymarket_bot.py

# 模拟运行（测试）
python3 polymarket_bot.py --dry

# 持续循环（每30分钟）
python3 polymarket_bot.py --loop

# 单独运行止盈引擎
python3 polymarket_take_profit.py --verbose
python3 polymarket_take_profit.py --dry --verbose
```

### 自动定时（launchd）
```bash
# 启动（开机自动运行）
launchctl load ~/Library/LaunchAgents/com.polymarket.bot.plist

# 停止
launchctl unload ~/Library/LaunchAgents/com.polymarket.bot.plist

# 查看状态
launchctl list | grep polymarket
```

## 资金分配策略
V3-SG : V2-SG : V1 = **50% : 35% : 15%**（V3-SG 优先）

## 止盈规则（"见好就收"）

| 仓位类型 | 结算时间 | 止盈条件 |
|---------|---------|---------|
| 高频 rename | < 1h | 净收益 > 20% |
| 短期 | 1-6h | 净收益 > $2 或 > 15% |
| 中期 | 6-24h | 净收益 > $3 或 > 20% |
| 长期 | > 24h | 净收益 > $5 或 > 25% |
| 止损 | > 2h剩余 | 亏损 > 60% → 回收残值 |

Gas 成本约 $0.05/笔，净收益已扣除。

## 成本对比
| 模式 | 日成本 | 月成本 |
|------|--------|--------|
| LLM 心跳（原） | ~$7 | ~$215 |
| 本地脚本（现） | $0 | $0 |
| LLM 仅异常介入 | ~$0.10 | ~$3 |

## LLM 仅在以下情况介入
1. 余额连续耗尽且无待结算仓位（提醒充值）
2. 需要分析新候选跟单账号
3. 用户主动查询状态
4. 每日17:00 UTC 更新 V3-SG 账号评分
