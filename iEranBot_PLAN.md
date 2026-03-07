# iEranBot — MVP(dmg) 迭代计划（基于 2026-03-07 拍板）

## 0. 目标
在 macOS 上交付一个可安装的 .dmg：
- 用户提交「市场官网 URL」
- 选择/粘贴「案例软文链接」+ 自然语言描述
- AI 生成可执行策略（Python）+ 可调参数
- 本地绑定账户（API Key 本地存储）
- 一键运行/停止/查看日志

> Polymarket 作为已跑通模板：保持现状不变；新框架以“可插拔多市场适配器”形式接入。

---

## 1) 总体架构（建议）
### 1.1 Electron App（dmg）
- Renderer：UI（市场/策略/账户/运行状态/日志）
- Main：本地文件、进程管理、加密存储、更新
- 与 Python 引擎通讯：
  - MVP：本地子进程 + JSON over stdio（简单、跨平台）

### 1.2 Python 策略引擎（内嵌）
- strategy/：策略模板与生成物
- runtime/：调度（定时/事件）与执行器
- adapters/：市场适配器（统一接口）

### 1.3 市场适配器接口（统一抽象）
最小可用接口（MVP）：
- `get_markets()` / `search_markets(query)`
- `get_orderbook(market_id)` 或 `get_price(market_id)`
- `place_order(order)` / `cancel_order(order_id)`
- `get_positions()` / `get_balances()`

---

## 2) 市场模块创建（AI 自动爬取 + 生成适配器）
### 2.1 MVP 先降维（务实）
- 用户输入「市场官网 URL」
- 系统做两步：
  1) 抓取：官网 + 文档页（可让用户补充 API doc 链接）
  2) 生成：产出适配器骨架 + 配置文件 + 测试脚本

### 2.2 生成物（适配器包）
- `adapters/<market_name>/adapter.py`
- `adapters/<market_name>/schema.json`（认证方式、下单字段、限频等）
- `adapters/<market_name>/smoke_test.py`

### 2.3 风险控制
- 适配器生成后默认 **只读模式**（禁用 place_order），用户通过 UI 勾选启用交易。

---

## 3) 策略生成（软文链接 + 自然语言）
### 3.1 输入
- URL：案例/软文链接
- 文本：用户补充说明（目标、风控、周期、资金规模、偏好市场等）

### 3.2 输出（策略包）
- `strategy.py`（可执行策略）
- `params.yaml`（用户可编辑参数）
- `README.md`（策略解释、风险提示、如何调参）
- `backtest_stub.py`（可选，先留接口）

---

## 4) 账户绑定（API Key 本地存储）
MVP 方案：
- macOS：Keychain 存储（优先）
- 跨平台兜底：加密文件（主密码/OS credential）

---

## 5) MVP 功能拆解（dmg 先行）
### 5.1 必做（V0）
- 新建项目（Project）
- 添加市场（Polymarket：选择模板；其他：输入 URL 生成 adapter 骨架）
- 录入 API Key（本地保存）
- 策略生成（先用“固定 prompt + 产出 python+params”跑通链路）
- 运行/停止（Python 子进程）
- 日志查看（tail/过滤）

### 5.2 应做（V1）
- 策略参数 UI 表单（从 params.yaml 自动生成）
- 只读/模拟/实盘三态
- 适配器 smoke test 一键跑

### 5.3 可做（V2）
- 多策略并行（队列/隔离）
- 自动更新（Electron auto-updater）
- 策略市场商店（下载/导入）

---

## 6) 两周可交付里程碑（建议节奏）
### Week 1：跑通端到端
- Electron 工程骨架 + 页面：项目/市场/账户/策略/运行
- Python 引擎：最小执行器 + 日志
- Polymarket：复用现有模板（只做包装，不改逻辑）

### Week 2：生成与安全
- 市场 URL → 适配器骨架生成（只读模式）
- 软文链接 → 策略生成（可调参数）
- Keychain/加密存储
- dmg 打包与安装测试（M1/M2）

---

## 7) 需要你确认的 5 个细节（决定实现方式）
1) 软文链接：主要来源是公众号/知乎/推特/博客？是否需要登录/反爬处理？
2) 策略生成：你更偏向输出“可读性强的 Python”还是“严格的 DSL 配置”？（我建议 MVP 直接 Python）
3) 运行调度：MVP 先做“手动一键运行”，还是必须包含 cron 定时？
4) 资金风控：是否强制必须有 max_position / max_daily_loss / kill-switch？
5) Polymarket 模板：是否允许在新 App 内“导入已有本地脚本目录”，还是我们复制一份到 Project？
