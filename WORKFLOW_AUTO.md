# WORKFLOW_AUTO.md - 自动化运维原则

## 核心原则
**策略一旦运行成功，立即部署本地，脱离 LLM，节约成本。**

## 本地自动化架构

### 运行中的 launchd jobs
| Job | 频率 | 模式 | 任务 |
|-----|------|------|------|
| com.polymarket.fast | 每5分钟 | fast | 止盈卖出 + rename高频跟单 |
| com.polymarket.mid | 每15分钟 | mid | V3-SG + V2-SG 跟单 |
| com.polymarket.v1 | 每整点+5分 | v1 | BTC/ETH hourly看涨 |

### 核心脚本
- `~/.openclaw/workspace/polymarket_bot.py` — 主交易循环
- `~/.openclaw/workspace/polymarket_take_profit.py` — 止盈引擎
- `~/.openclaw/skills/polyclaw/` — 底层 buy/sell 执行
- `~/.openclaw/workspace/polymarket_bot.log` — 运行日志

### 环境变量（已配置）
- `POLYCLAW_PRIVATE_KEY` — 写入 .env + .zshrc + 各 plist
- `CHAINSTACK_NODE` — 写入 .env + 各 plist

## LLM 介入原则（最小化）
只在以下情况才需要 LLM：
1. **用户主动询问** — 状态汇报、策略讨论
2. **新策略设计** — 逻辑开发完后立即转为本地脚本
3. **异常处理** — 脚本无法自动恢复的故障
4. **每日17:00 UTC** — V3-SG账号评分更新（可选）
5. **24h战报** — 每天定时汇报盈亏

## 开发流程
1. 设计策略 → LLM 辅助编码
2. `--dry` 模拟验证
3. 真实小额测试
4. 部署 launchd → **脱离 LLM**

## 成本对比
| 模式 | 日成本 |
|------|--------|
| LLM 心跳（原） | ~$7/天 |
| 本地脚本（现） | $0/天 |
| LLM 仅按需 | ~$0.10/天 |

## HEARTBEAT 原则
心跳检测只做：
1. `tail -5 ~/.openclaw/workspace/polymarket_bot.log` 确认脚本正常
2. 余额持续为0且无持仓 → 提醒充值
3. 日志出现连续ERROR → 告警
4. 其余情况：HEARTBEAT_OK，不调用任何 API
