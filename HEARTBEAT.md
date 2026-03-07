# HEARTBEAT.md
# Polymarket 本地机器人 - 心跳监控（最小化LLM调用）

## 日常心跳（绝大多数情况）
```
tail -5 ~/.openclaw/workspace/polymarket_bot.log
```
- 最后一行是"执行完毕" → HEARTBEAT_OK，不做任何其他操作
- 出现"余额不足"且连续3次 → 提醒用户充值
- 出现连续ERROR/异常 → 简短告警

## 不要做的事
- ❌ 不扫描持仓（脚本自动处理）
- ❌ 不调用 Polymarket API（脚本自动处理）
- ❌ 不分析信号（脚本自动处理）
- ❌ 不手动下注（脚本自动处理）

## 本地脚本状态
- fast job: 每5分钟止盈 + rename高频
- mid job:  每15分钟 V3-SG + V2-SG
- v1 job:   每整点+5分 BTC hourly

## 只在用户主动询问时才介入
- 查看战报 → 读日志汇总
- 策略调整 → 修改脚本后部署
- 故障排查 → 看日志定位问题
