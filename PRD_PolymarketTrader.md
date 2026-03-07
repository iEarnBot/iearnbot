# Polymarket Trader — 仪表盘与策略系统 需求文档（PRD）

> 版本：Draft v1.1
> 更新时间：2026-03-02
> 部署形态：本地桌面工具（macOS/Linux），策略引擎/进化引擎/止盈止损/仪表盘全部本地运行，默认无需LLM

---

## 1. 背景与问题
用户向 Polymarket 钱包汇入约 **300U 本金**，在自动跟单/策略运行中资金大幅回撤。用户希望：
1. **亏赚清晰可解释**（复盘回顾模块，经验教训沉淀）
2. **可以一键停止/复盘/进化再启动**（面板内完成）
3. 策略具备 **止盈/止损** 的独立、可配置、可进化机制
4. 支持 **新增策略**：用户粘贴案例说明、链接、钱包/账号，系统自动分析生成策略代号（Vx）

---

## 2. 产品目标
- 让用户在仪表盘内"看得懂"：资金流、每日战绩、分策略盈亏、关键失败原因
- 让用户在仪表盘内"能控制"：一键停止/启动、手动触发各策略、一键进化
- 让用户在仪表盘内"能扩展"：新增策略（多案例/多链接/多钱包）、自动命名生成 V4/V5…

---

## 3. 固定 9 个 Tab（当前版本）

| # | Tab | 内容 |
|---|-----|------|
| 0 | 📊 总览 | KPIs、持仓分层（赢/中/亏）、市场类型盈亏、任务状态 |
| 1 | 💳 每单明细 | 每笔 SPLIT/SELL/REDEEM，净盈亏、进场时间 |
| 2 | 🟦 V1 BTC看涨 | V1 独立看板：战绩、参数、持仓 |
| 3 | 🟨 V2 榜单跟单 | V2 独立看板：战绩、参数、近期跟单 |
| 4 | 🟪 V3 名单跟单 | V3 独立看板：账号列表、目标 vs 我方对比 |
| 5 | 🧩 策略+ | 内置V1-V3卡片、自定义V4+卡片、新增策略表单 |
| 6 | 💹 止盈/止损 | 阈值配置、用户备注、一键进化（含进化中状态） |
| 7 | 📅 日清日结 | 24h盘点、每日战绩、连续亏损告警、一键停止 |
| 8 | ⚙️ 设置 & 复盘 | 全局参数、市场类型开关、复盘模块、一键进化 |

---

## 4. 关键功能需求

### 4.1 粘贴内容不丢失
- 移除 `<meta http-equiv="refresh">` 整页刷新
- 使用 `/?partial=1` 轻量 JSON 仅更新 KPI，不刷新表单区域
- 表单提交成功/失败不跳转，保持 Tab 位置，显示 msg
- 进化/参数保存等写操作为 POST，不触发整页刷新

### 4.2 一键停止/启动
- 停止：暂停 fast/mid/v1 launchd 任务，写入 `polymarket_stop.flag`
- 启动：移除 flag，恢复任务
- 停止后不新增买入；持仓继续止盈/赎回

### 4.3 一键进化（带"进化中"状态）
- 点击"开始进化"后：
  - 按钮变为"🔄 进化中…"并禁用，不可重复点击
  - 后台执行进化脚本（本地规则驱动，无 LLM）
  - 完成后按钮恢复，显示进化结果 msg
- 复盘进化规则：自动禁用亏损大的市场类型、提高流动性门槛
- 止盈止损进化规则：根据近期胜率调整止损线/时间止损/止盈阈值
- 每次进化记录：timestamp、用户备注、变更项（存 JSON）

### 4.4 新增策略系统（V4+）
**输入**：
- 策略说明（必填）
- 案例/链接（textarea，每行一个，支持多个）：
  - Polymarket 市场链接
  - Polymarket Profile `https://polymarket.com/@xxx`（尝试自动解析钱包地址）
  - Polygonscan 地址链接
  - **X（Twitter）链接**（可选增强：抓取文章内容填充策略说明）
- 目标钱包地址（textarea，多个）
- 用户备注

**输出**：
- 策略代号：V4, V5…（顺序增长）
- 自动分析（规则驱动）：市场类型、风险提示、风控建议
- 策略卡片：代号/名称/状态/提交时间/生成时间/分析摘要/链接

**组合策略**：多钱包一起提交 → 存为列表 → 后台逐一分析

---

## 5. 迭代路线图（Next）

### v1.1（下一个迭代）
- [ ] 进化中状态：按钮 loading + 禁用，完成后恢复
- [ ] X 链接自动抓取：粘贴 `https://x.com/...` 后自动抓取内容填充（可选开关）
- [ ] Polymarket Profile 自动解析：`@handle` → 钱包地址（API 查询）

### v1.2（策略接入执行器）
- [ ] 自定义策略真正接入执行引擎：
  - 定义执行频率（5/15/60 min）
  - 定义买入规则（价格区间/流动性/时间窗/禁用类型）
  - 绑定止盈止损模板
- [ ] 每个 V4+ 策略在 Tab5 内有独立运行状态面板（最近触发、成功/失败次数）

### v1.3（风控增强）
- [ ] 单市场最大敞口限制
- [ ] 单跟单账号上限（避免过度跟随某一账号）
- [ ] conditionId 级别反对冲（已部分实现，完善自动 MERGE）
- [ ] 同 eventId 下只能持有一个方向

---

## 6. 桌面应用化（Desktop App）目标

### 目标形态
- **macOS 原生 App**：出现在程序坞（Dock），有独立图标，双击启动
- 内部运行：本地 HTTP Server（localhost:7799）+ 系统 WebView 打开仪表盘
- 安装方式：下载 `.dmg` 或 `brew install`

### 技术方案（推荐）
| 方案 | 实现 | 优点 |
|------|------|------|
| **Tauri** | Rust + WebView | 包小（<5MB）、原生体验、跨平台 |
| PyInstaller + AppleScript | 打包 Python + 系统 WebView | 纯 Python，无需学 Rust |
| **Electron** | Node.js | 社区大，但包体大（200MB+） |

**当前推荐：PyInstaller + py2app（macOS）**
- 把 `polymarket_dashboard.py` + bot 脚本 + 资源一起打包
- 生成 `PolymarketTrader.app`，放 `/Applications`
- 图标：自定义 `.icns` 文件（已规划）

---

## 7. GitHub 开源发布

### 仓库地址
`https://github.com/hiclawbot2026/PolymarketTraderClaw`

### 目录结构（目标）
```
PolymarketTraderClaw/
├── README.md               # 中文文档 + 快速开始
├── setup.sh                # 一键安装脚本（macOS/Linux）
├── pyproject.toml          # uv 依赖管理
├── .env.example            # 私钥/RPC配置模板
├── .gitignore              # 忽略 .env / data/ / __pycache__/
├── src/
│   ├── bot.py              # 主策略机器人（V1/V2/V3）
│   ├── dashboard.py        # 本地仪表盘 Web UI
│   ├── take_profit.py      # 止盈/止损/MERGE
│   ├── evolution.py        # 自进化引擎
│   ├── v3_tracker.py       # V3 目标账号追踪
│   ├── redeem.py           # 赎回脚本
│   └── setup_wallet.py     # 钱包设置/授权
├── assets/
│   └── v3sg_accounts.json  # V3 监控账号名单
│   └── icon.icns           # macOS App 图标（待设计）
├── data/                   # 运行时数据（gitignore）
│   └── .gitkeep
└── app/                    # 桌面应用封装（v1.2 目标）
    ├── PolymarketTrader.spec  # PyInstaller spec
    └── launcher.py           # 打开 WebView + 启动后台
```

### 发布步骤（见第 8 节）

---

## 8. GitHub 发布操作指南

### 前提
- 已在 `~/polymarket-trader/` 有 git init + 初始 commit
- 已开通 GitHub 仓库：`hiclawbot2026/PolymarketTraderClaw`

### 步骤
```bash
# 1. 进入项目目录
cd ~/polymarket-trader

# 2. 添加远端
git remote add origin https://github.com/hiclawbot2026/PolymarketTraderClaw.git

# 3. 确认 .gitignore 包含 .env 和 data/
cat .gitignore

# 4. 同步最新代码
git add .
git commit -m "feat: Dashboard v3 - 9 tabs, V1/V2/V3 boards, custom strategy V4+, anti-refresh"

# 5. 推送
git push -u origin main
```

### 注意事项
- ⚠️ **绝对不要提交 `.env` 文件**（含私钥）
- ⚠️ `data/` 目录含运行时 JSON（余额/仓位等），也不要提交
- README 里说明用户需要自行创建 `.env`（参考 `.env.example`）

---

## 9. 数据文件（本地运行时）
| 文件 | 说明 |
|------|------|
| `polymarket_params.json` | 全局参数/策略开关 |
| `polymarket_stats.json` | 胜率/结算统计 |
| `polymarket_tp_config.json` | 止盈止损配置 + 进化记录 |
| `polymarket_review.json` | 复盘输入/进化记录 |
| `polymarket_strategies.json` | 自定义策略 V4+ |
| `polymarket_v3_trace.json` | V3 追踪数据 |
| `polymarket_bot.log` | 运行日志 |
| `polymarket_stop.flag` | 存在=停止，不存在=运行 |

---

## 10. 验收标准
1. 固定 9 Tab，刷新/新增策略不丢 Tab
2. V1/V2/V3 均有独立 Tab 看板，内容可用
3. 新增策略表单支持多链接/多钱包，提交后生成 V4+
4. 粘贴大段文本不因刷新/切 Tab 消失
5. 一键停止后不再新增买入；一键启动恢复
6. 复盘/止盈止损：点击进化后显示"进化中"，完成后恢复
7. GitHub 仓库可正常 clone + setup.sh 安装运行

---

*文档由 OpenClaw + Claude 辅助生成，2026-03-02*
