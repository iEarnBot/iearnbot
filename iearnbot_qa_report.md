# iEarn.Bot QA 报告 — 001号用户模拟器
**日期**: 2026-03-06  
**测试角色**: 全新 macOS 用户（零经验）  
**Repo**: https://github.com/iEarnBot/iearnbot  
**官网**: https://iearn.bot  

---

## 🔴 一、致命问题（新用户必卡）

### 1. `setup.sh` 根本不存在！
**最严重问题。**

官网首页的安装教程写的是：
```
cd ~/iearnbot && bash setup.sh
```
但 Repo 里根本**没有 `setup.sh` 这个文件**！

Repo 实际文件清单：
- `public/` （网站静态文件）
- `.env.example`
- `.gitignore`
- `README.md`
- `skillpay.py`
- `strategy_ai_example.py`
- `vercel.json`

新用户按照官网操作，第2步就会报错：
```
bash: setup.sh: No such file or directory
```
**完全卡死，无法继续。**

---

### 2. `src/` 目录不存在，但代码里用到了

官网终端演示里写的是：
```
python src/strategy_ai.py generate "BTC breaks 90k, buy YES"
```

`strategy_ai_example.py` 文件的 CLI 注释里也写：
```
python src/strategy_ai.py generate "..."
```

但 Repo 里没有 `src/` 目录，文件名是 `strategy_ai_example.py`，不是 `src/strategy_ai.py`。

用户照着官网执行 = 直接报错。

---

### 3. Bot 主体代码完全缺失

Repo 里只有：
- 一个计费模块（`skillpay.py`）
- 一个策略生成示例（`strategy_ai_example.py`）
- 一个官网前端（`public/`）

但官网声称具备的功能，**在 Repo 里全都找不到代码**：
- V1 BTC Momentum 策略
- V2 Leaderboard copy 策略
- V3 Wallet tracking 策略
- 本地 Dashboard（localhost:7799）
- 进化引擎（Evolution Engine）
- 止损/止盈执行逻辑
- Polymarket CLOB 下单逻辑
- launchd 自动启动配置

一个新用户按照官网安装完，会发现**没有任何可运行的 Bot**。

---

## 🟠 二、严重问题（流程不清晰）

### 4. README.md 内容与项目完全不符

README 的标题是 **"iEarn.Bot Official Website"**，内容只描述了网站的部署方式（Vercel + npx serve）。

对于想**安装并使用 Bot** 的用户，README 给出的是完全错误的方向：
- 没有 Bot 安装说明
- 没有依赖要求
- 没有配置说明
- 只有 `npx serve public` 这样的网站预览命令

这会让新用户以为这个 Repo 只是个官网，而不是 Bot 本身。

---

### 5. `.env.example` 中 `SKILLPAY_API_KEY` 从哪里获取？

`.env.example` 要求填写：
```
SKILLPAY_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SKILLPAY_USER_ID=your_telegram_id_or_wallet_address
```

但没有任何文档说明：
- 去哪里注册/获取 `SKILLPAY_API_KEY`？
- SkillPay 账户如何创建？
- 充值流程是什么？

新用户会卡在"我的 API Key 在哪？"这一步。

---

### 6. `SKILLPAY_USER_ID` 定义模糊

`.env.example` 注释：
```
# e.g. Telegram ID or wallet address
```

但没有说明：
- 是用 Telegram ID 还是钱包地址？
- 两者有什么区别？
- 如何查询自己的 Telegram ID？

如果填错，计费会失败，且错误信息不够友好。

---

### 7. `POLYMARKET_API_KEY` 如何获取？

`.env.example` 中有：
```
POLYMARKET_API_KEY=your_polymarket_api_key
```

Polymarket 的 API Key 获取方式相对复杂（需要钱包签名认证），但 Repo 里没有任何说明文档。

---

### 8. Dashboard 声称运行在 `localhost:7799`，但代码中不存在

官网多处提到 "Open http://localhost:7799/?ui=v2" 来查看 Dashboard，但：
- Repo 中没有任何启动 web server 的代码
- 没有 Dashboard 相关的 HTML/Python 文件
- 没有说明如何启动这个服务

---

## 🟡 三、体验问题（可能让用户困惑）

### 9. `strategy_ai_example.py` 文件名有 `_example` 后缀

这个文件名暗示它只是一个示例，而不是实际可用的工具。但官网将其作为核心功能展示。命名会让用户困惑："我是要用这个文件，还是还有另一个正式版本？"

---

### 10. `python-dotenv` 依赖没有说明如何安装

`skillpay.py` 和 `strategy_ai_example.py` 都用了 `python-dotenv`，但：
- 没有 `requirements.txt`
- 没有 `pyproject.toml`
- 没有任何依赖安装指引

只有 `strategy_ai_example.py` 顶部注释里写了一行：
```
pip install requests python-dotenv openai
```
但这不够突出，新用户很容易忽略。

---

### 11. 官网和代码中 `openai` 包版本要求不明

代码里用了 `openai.OpenAI(base_url=...)` 这个 v1.x 以上的写法，但没有指定版本。如果用户 `pip install openai` 装到了旧版（<1.0），会报错。

---

### 12. 官网声称"MIT 开源"，但 Repo 中没有 LICENSE 文件

没有 `LICENSE` 文件。对关心合规的用户是疑虑点。

---

### 13. 官网统计数字可信度问题

Hero 区域展示：
- "3+ Built-in Strategies"（内置策略数）

但代码里这三个策略根本不存在，这是 marketing 数字，不是实际状态。

---

## 📋 四、缺失文件清单

| 文件 | 状态 | 影响 |
|------|------|------|
| `setup.sh` | ❌ 缺失 | 安装流程直接失败 |
| `src/strategy_ai.py` | ❌ 缺失（只有 example） | 官网命令无法执行 |
| `requirements.txt` | ❌ 缺失 | 依赖安装不清晰 |
| `LICENSE` | ❌ 缺失 | 虽声称 MIT 但未确认 |
| `src/bot_v1.py` (或类似) | ❌ 缺失 | V1 策略代码不存在 |
| `src/bot_v2.py` (或类似) | ❌ 缺失 | V2 策略代码不存在 |
| `src/bot_v3.py` (或类似) | ❌ 缺失 | V3 策略代码不存在 |
| Dashboard 代码 | ❌ 缺失 | localhost:7799 无法打开 |
| Evolution Engine | ❌ 缺失 | 官网功能无对应代码 |
| launchd plist 配置 | ❌ 缺失 | 自启动无法配置 |
| SkillPay 注册/充值文档 | ❌ 缺失 | 用户不知道如何获取 API Key |

---

## 🎯 五、优先修复建议

1. **最高优先级**: 创建 `setup.sh`（或至少创建 README 真实安装说明）
2. **高优先级**: 将 Bot 核心代码提交到 Repo（V1/V2/V3 策略 + Dashboard）
3. **高优先级**: 添加 `requirements.txt`
4. **中优先级**: 重写 README.md，改为真实的安装文档
5. **中优先级**: 添加 SkillPay API Key 获取说明（链接或文档）
6. **低优先级**: 添加 LICENSE 文件
7. **低优先级**: 将 `strategy_ai_example.py` 重命名为实际路径（`src/strategy_ai.py`）

---

## 总结

当前状态：**Repo 是一个空壳**。只有官网前端和两个 Python 示例文件，没有实际可运行的 Bot。

官网展示的所有核心功能（Dashboard、3种策略、进化引擎、安装脚本）在 Repo 中均不存在。

**新用户按照官网操作，在第2步（`bash setup.sh`）就会卡死。**

项目目前适合：开发者作为占位 Repo + 官网展示。不适合：任何真实用户尝试安装和使用。
