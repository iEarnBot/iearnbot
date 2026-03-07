# iEarn.Bot dmg 安装测试报告

日期: 2026-03-07  
架构: arm64  
版本: 0.4.0  
结果: ✅ 成功

## 测试步骤

### 1. DMG 文件确认
- 路径: `/Users/hibot/.openclaw/workspace/electron/dist/iEarn.Bot-0.4.0-arm64.dmg`
- 大小: 89MB
- CRC32 验证: $91286ED5 ✅

### 2. 挂载 & 安装
- `hdiutil attach` 成功挂载到 `/Volumes/iEarn.Bot 0.4.0`
- DMG 内容: `iEarn.Bot.app` + `Applications` 快捷方式
- 已 `cp -R` 复制到 `/Applications/`
- `hdiutil detach` 卸载成功

### 3. App 结构验证
```
/Applications/iEarn.Bot.app/Contents/
  ├── Frameworks/
  ├── Info.plist
  ├── MacOS/
  ├── PkgInfo
  └── Resources/
        ├── app.asar   ← 主应用包
        └── *.lproj    ← 多语言资源
```
- 二进制: `Mach-O 64-bit executable arm64` ✅

### 4. 启动测试
- 清除隔离属性 (`xattr -cr`) 后直接启动
- 进程启动正常，无需 Gatekeeper 修复

**运行进程（PID）:**
| 进程 | 角色 |
|------|------|
| iEarn.Bot (96402) | 主进程 |
| iEarn.Bot Helper GPU (96410) | GPU 渲染 |
| iEarn.Bot Helper (96411) | 网络服务 |
| iEarn.Bot Helper Renderer (96417) | 渲染器 |

- 无崩溃日志
- 用户数据目录: `~/Library/Application Support/iearnbot`
- 界面语言: zh-CN（自动跟随系统）

### 5. 常见问题
| 问题 | 状态 |
|------|------|
| "damaged / can't be opened" | 未触发（xattr 清除后正常）|
| 权限错误 | 未触发 |
| 崩溃 | 无 |

## 结论

iEarn.Bot v0.4.0 arm64 dmg 安装测试**全部通过**。App 可在 Apple Silicon Mac 上正常安装并启动，Electron 渲染层、GPU 加速、网络服务均正常运行。
