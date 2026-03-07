# rename 跟单专项配置

## 账号信息
- 名称：rename
- 地址：0xf6963d4cdbb6f26d753bda303e9513132afb1b7d
- 类型：高频加密15M套利机器人
- 今日收益：$284,193（500笔，平均5秒一笔）
- 主攻：BTC/ETH/SOL/XRP 15分钟 Up or Down 市场

## 活跃时间窗口
美东交易时段：约 14:00-21:00 UTC（即北京时间 22:00-次日05:00）

## 跟单逻辑
rename 的套利边缘来自**预言机价格滞后**：
- 他在15M窗口开盘前后快速建仓，利用价格更新时间差
- 持仓 10-15 分钟内结算
- 我们晚几秒跟，价格略有损耗但方向正确

## 执行方式（嵌入V3-SG）
在美东交易时段（14:00-21:00 UTC）心跳时：
1. 查询 rename 最新持仓：
   GET https://data-api.polymarket.com/trades?user=0xf6963d4cdbb6f26d753bda303e9513132afb1b7d&limit=10
2. 找最近5分钟内的新建仓位（timestamp > now-300）
3. 确认是15M Up/Down 市场
4. 跟单方向相同，下注 $3
5. 结算时间 < 30min 不跟（太晚）

## 注意
- 跟单金额控制在 $3，因为窗口短、方向不确定性仍存在
- 每个市场只跟一次，不重复
- 已跟过的 conditionId 记录到 rename_followed.json 避免重复
