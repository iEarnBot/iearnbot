# iEarn.Bot — 产品需求文档 (PRD)
# Product Requirements Document
> 版本: v0.1 | 创建: 2026-03-06 | 负责人: AI PM

---

## 一、产品定位

**iEarn.Bot** 是一款本地运行的 AI 驱动预测市场自动交易机器人。

> "连接钱包，一键授权，AI 帮你自动生成策略、自动交易、可视化看收益。"

### 核心设计原则（北极星）
**用户零配置，AI 帮他做一切。**
- 用户只需做一件事：**连接钱包 + 一次性授权**
- 其余全部自动：策略生成、市场扫描、下单、止损、止盈、复盘
- 可视化 Dashboard 实时展示 AI 在做什么、赚了多少

### 核心价值
- 🔐 **非托管** — 私钥通过 WalletConnect/MetaMask 授权，不直接暴露
- 🤖 **AI 策略** — 用自然语言描述，Claude 自动生成并持续运行
- 👁️ **全程可视** — Dashboard 实时展示策略执行、持仓、P&L
- 💳 **按次付费** — SkillPay 计费，0.01 USDT/次，无订阅无注册
- 📦 **开箱即用** — .dmg/.exe 安装，无需终端，无需 Python
- 🌐 **开源** — MIT 许可，完全透明可审计

### 理想用户旅程（终态）
```
下载 iEarnBot.dmg（或 .exe）
→ 双击安装，拖入 Applications
→ 打开 App，弹出 "Connect Wallet"
→ MetaMask / WalletConnect 扫码授权（只授权签名，私钥不离开钱包）
→ 选择初始资金（50 USDT 起）
→ AI 自动分析当前 Polymarket 热门市场
→ 推荐 3 个策略，用户一键确认
→ Bot 开始运行，Dashboard 实时显示
→ 用户躺着看收益 📊
```

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

### v0.2 — 钱包连接（核心里程碑）
> 目标：用户不需要粘贴私钥，用 WalletConnect 授权

- [ ] WalletConnect v2 集成（扫码连接 MetaMask/Trust Wallet）
- [ ] 授权签名而非暴露私钥
- [ ] 自动检测钱包余额，推荐初始投入金额
- [ ] Dashboard 加入"Connect Wallet"引导页
- [ ] 首次连接后自动推荐 3 个适合当前市场的策略
- [ ] 一键确认开始运行

### v0.3 — AI 自动驾驶
> 目标：用户什么都不用填，AI 全自动

- [ ] AI 自动扫描 Polymarket 所有活跃市场
- [ ] 根据胜率、流动性、到期时间自动评分
- [ ] 自动生成最优策略组合
- [ ] 自动分配资金（按风险偏好）
- [ ] 每日 AI 复盘报告（推送到 Telegram）
- [ ] 自进化：赢了加仓，输了调参

### v0.4 — 桌面 App（完全无终端）
> 目标：.dmg/.exe 小白也能用

- [ ] macOS .dmg 安装包（托盘图标，双击启动）
- [ ] Windows .exe 安装向导
- [ ] 内置 Python 环境（用户无需安装 Python）
- [ ] 图形化设置界面（不需要编辑 .env）
- [ ] 一键更新（自动检查新版本）

### v1.0 — 多市场覆盖
> 目标：不只是 Polymarket，覆盖所有预测市场

- [ ] Manifold Markets
- [ ] Kalshi
- [ ] Metaculus
- [ ] 跨市场套利
- [ ] 策略市场（用户上传/下载/购买策略）

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
