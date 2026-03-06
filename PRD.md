# iEarn.Bot — 产品需求文档 (PRD)
# Product Requirements Document
> 版本: v0.1 | 创建: 2026-03-06 | 负责人: AI PM

---

## 一、产品定位

**iEarn.Bot** 是一款本地运行的 AI 驱动预测市场自动交易机器人。

> "让任何人都能用自然语言描述策略，AI 自动生成规则并在 Polymarket 上 24/7 自动交易。"

### 核心价值
- 🔐 **非托管** — 私钥永不离开用户本地机器
- 🤖 **AI 策略** — 用自然语言描述，Claude 生成结构化交易规则
- 💳 **按次付费** — SkillPay 计费，0.01 USDT/次，无订阅无注册
- 📊 **可视化** — 本地 Dashboard，实时 P&L、持仓、策略状态
- 🌐 **开源** — MIT 许可，完全透明可审计

---

## 二、目标用户

| 用户类型 | 描述 | 痛点 |
|---------|------|------|
| 散户交易者 | 想参与预测市场但没时间盯盘 | 手动操作累，错过好机会 |
| 技术用户 | 懂 Python，想自动化策略 | 从零写太麻烦 |
| 被动收益追求者 | 想让钱自动工作 | 不信任托管平台 |

---

## 三、版本路线图

### v0.1 — MVP（当前冲刺）
> 目标：让 001 号用户能 `bash setup.sh` 一键安装运行

- [ ] `setup.sh` 一键安装脚本
- [ ] 完整项目结构（src/ 目录）
- [ ] `skillpay.py` — 计费模块
- [ ] `strategy_ai.py` — AI 策略生成
- [ ] `strategy_v1.py` — BTC 动量策略（免费）
- [ ] `strategy_v2.py` — 排行榜跟单策略（免费）
- [ ] `strategy_v3.py` — 钱包追踪策略（免费）
- [ ] `dashboard.py` — 本地 Dashboard（localhost:7799）
- [ ] `README.md` — 清晰安装文档（EN/中文）
- [ ] `.env.example` — 环境变量说明
- [ ] `requirements.txt` — Python 依赖
- [ ] launchd 自动启动（macOS）
- [ ] 安装完成自动打开浏览器

### v0.2 — 稳定性
> 目标：稳定运行，有错误报告

- [ ] 完整错误处理和日志
- [ ] Telegram 告警通知（余额不足、止损触发等）
- [ ] 自动止损/止盈执行
- [ ] 自进化引擎（分析胜率，自动调参）
- [ ] Dashboard v2（更美观，支持移动端）

### v0.3 — AI 增强
> 目标：更强的 AI 策略能力

- [ ] 策略回测（用历史数据测试）
- [ ] 多策略并行 + 资金分配
- [ ] 实时新闻信号接入（影响预测市场的新闻）
- [ ] 策略分享市场（用户可上传/下载策略）

### v1.0 — 多市场
> 目标：不只是 Polymarket

- [ ] Manifold Markets 支持
- [ ] Kalshi 支持
- [ ] 跨市场套利策略
- [ ] Windows 支持
- [ ] Docker 一键部署

---

## 四、技术架构

```
iearnbot/
├── setup.sh              # 一键安装
├── README.md             # 文档
├── .env.example          # 配置示例
├── requirements.txt      # 依赖
├── launchd/
│   ├── fast.plist        # 每5分钟 止盈+rename
│   ├── mid.plist         # 每15分钟 V2/V3策略
│   └── v1.plist          # 每小时 V1策略
└── src/
    ├── skillpay.py       # SkillPay 计费
    ├── strategy_ai.py    # AI 策略生成入口
    ├── strategy_v1.py    # BTC 动量
    ├── strategy_v2.py    # 排行榜跟单
    ├── strategy_v3.py    # 钱包追踪
    ├── evolution.py      # 自进化引擎
    ├── executor.py       # 下单执行
    ├── risk.py           # 止损/止盈
    └── dashboard.py      # 本地 Web UI
```

---

## 五、SkillPay 计费规则

| 操作 | 费用 |
|------|------|
| AI 策略生成 | 0.01 USDT |
| 策略优化建议 | 0.01 USDT |
| 新闻信号分析（v0.3）| 0.005 USDT |
| 策略回测（v0.3）| 0.02 USDT |

- Skill ID: `524d73be-05d5-43de-8d97-57f769206eb0`
- 支付: BNB Chain USDT
- 95% 归开发者

---

## 六、当前已知问题（来自 QA）

### 🔴 致命（v0.1 必须修复）
1. `setup.sh` 不存在
2. `src/strategy_ai.py` 路径错误（现在是 `strategy_ai_example.py`）
3. V1/V2/V3 Bot 代码完全缺失
4. Dashboard localhost:7799 不存在
5. README 描述的是网站而非 Bot

### 🟠 严重（v0.1 需修复）
6. SKILLPAY_USER_ID 定义模糊
7. SkillPay 注册/充值流程无文档
8. 缺少 requirements.txt

---

## 七、迭代流程

```
QA Agent 发现问题
      ↓
主 AI (PM) 分析优先级
      ↓
Dev Agent 修复并写代码
      ↓
推送 GitHub → Vercel 自动部署
      ↓
用户（001号）测试验证
      ↓
循环
```

---

## 八、成功指标

- v0.1: 001号用户能完整安装并运行
- v0.2: 连续运行72小时无崩溃
- v0.3: 策略胜率 > 55%
- v1.0: 100+ GitHub Stars，10+ 活跃用户
