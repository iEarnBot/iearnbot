# Polymarket V1 自动交易策略

## 规则
- 有资金 → 自动找最优 hourly/daily 市场下注，优先 YES（看涨加密）
- 资金耗尽 → 等结算回款
- 回款到账 → 自动开始下一轮
- 用户充值 → 用户主动决定，不催促

## 选市场优先级
1. BTC/ETH hourly Up or Down（当前小时窗口，YES>0.55 时入场）
2. BTC/ETY 15M Up or Down（临近到期前5分钟，结合价格趋势）
3. BTC/ETH 当日 daily（价格明显高于目标价时）

## 单笔金额
- 默认 $5/笔
- 余额不足 $5 时，用全部余额下注

## 待结算仓位
- 今天 16:00 UTC：BTC Up or Down 10AM ET，YES，$2
- 今天 17:00 UTC：BTC Up or Down Mar 1 ×7笔，YES，$35
- 长期：伊朗政权倒台 Mar 31，YES，$1（赔率4.5x）

## 历史战绩
- 2026-03-01：首轮，7笔 $5 + 1笔 $2，已下注 $37，待结算
