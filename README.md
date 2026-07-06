# PC Screenshot Tool / PC 截图工具

多模式屏幕截图工具，支持常规截图、区域选择、隐身模式（绕过反作弊）、定时截图、全局热键，内置 30+ 反作弊/监考软件自动扫描器。

---

## 目录结构

```
├── pc_screenshot.py                  # 主程序 (Python, 零外部依赖)
├── 截图工具.bat                       # 一键启动 GUI
├── pc_screenshot_config.json         # 配置文件 (可选)
│
├── StealthCapture.cs                 # DXGI + GDI 截图库 C# 源码
├── StealthCapture.dll                # 编译后的截图库 (.NET 4.0)
├── educoder_screenshot_enable.ps1    # 隐身截图 PowerShell 脚本
│
├── analyze_educoder.ps1              # EduCoder 反作弊分析器
└── README.md
```

---

## 快速开始

### 要求

- Python 3.x（仅需标准库 tkinter，零 pip 依赖）
- Windows 10/11
- 隐身模式需要管理员权限 + .NET Framework 4.0

### 启动 GUI
```bash
python pc_screenshot.py
# 或双击 截图工具.bat
```

### CLI 模式
```bash
python pc_screenshot.py --full              # 全屏截图
python pc_screenshot.py --region            # 鼠标框选区域
python pc_screenshot.py --stealth           # 隐身模式 (反作弊绕过)
python pc_screenshot.py --scan              # 扫描反作弊软件
python pc_screenshot.py --clip              # 全屏 → 剪贴板
python pc_screenshot.py --hotkey            # 启动 Ctrl+Shift+S 全局热键
python pc_screenshot.py --interval 5        # 每5秒截图
python pc_screenshot.py --lang en           # 切换英文界面
python pc_screenshot.py --out "D:\截图"     # 指定输出目录
```

---

## 功能演进历史

### v1.0 — 初始版本
- GDI32 全屏截图（ctypes 直接调用，零依赖）
- 区域选择（tkinter 半透明蒙层拖拽）
- 内建 PNG 编码器（纯 zlib，无需 Pillow）
- 剪贴板写入（PowerShell 桥接）

### v1.1 — 隐身/反作弊模式
- **StealthCapture.dll** — C# 编译的 DXGI Desktop Duplication 库
  - DXGI 优先：GPU 显存直接读取（不触发 user32 Hook 链）
  - GDI BitBlt 回退：屏幕 DC 只读操作（零窗口消息）
  - 全局单例设计：Factory/Device/Dup/Staging 纹理一次初始化复用
  - 原始 vtable 调用：绕过 .NET COM Interop 限制
  - 非阻塞帧获取：`AcquireNextFrame(0, ...)` 自旋轮询
  - 缓存的委托+像素缓冲区+画布
- `educoder_screenshot_enable.ps1` — 调用 DLL 的 PowerShell 入口
  - 不调用 BlockInput（避免被 SetWindowsHookEx 捕获）
  - 不操作剪贴板（避免被轮询清空）
  - 不触碰窗口句柄（避免触发 SetWinEventHook 切屏检测）

### v1.2 — 多语言 i18n
- 中/英文双语字典系统 `T[zh]/T[en]`
- GUI RadioButton 实时切换（`refresh_ui()` 遍历所有已注册控件）
- CLI `--lang zh|en` + 环境变量 `SCREENSHOT_LANG` + 系统语言自动检测
- 优先级：CLI > 环境变量 > 系统检测

### v1.3 — 配置系统
- `pc_screenshot_config.json` 可配置：
  - `output_dir` — 输出目录
  - `log_enabled` / `log_max_lines` — 日志开关和上限
  - `hotkey_enabled` / `hotkey_require_admin` — 热键权限控制
  - `stealth_ps1` / `stealth_dll` — 隐身模式脚本/DLL 路径（支持多路径回退搜索）
- 所有路径硬编码已消除

### v1.4 — 线程安全 + 日志
- `threading.Lock()` 包裹所有截图函数，并发调用返回 `CaptureBusy`
- `log_event()` 双重写入：内存环形缓冲 + 文件 `pc_screenshot.log`
- 日志格式：`[时间戳] 动作 | 详情`
- 文件名包含前景窗口标题：`full_窗口名_时间.png`

### v1.5 — 反作弊扫描器
- **三层扫描引擎**：
  1. `EnumProcesses` + `GetModuleBaseNameW` — 进程名匹配
  2. `EnumWindows` + `GetWindowTextW` — 窗口标题正则匹配
  3. BlockInput 状态检测 — 键盘/鼠标锁检测
- **30+ 签名数据库**，按风险等级分类：

| 风险 | 类別 | 目标 |
|------|------|------|
| 🔴 高 | 考试平台 | 头歌/educoder、超星/学习通、智慧树、雨课堂、examclient |
| 🔴 高 | 反作弊 Hook | educoderkey、examshield、examguard、lockdown、safeexam、securebrowser |
| 🔴 高 | 屏幕锁定 | screenlock |
| 🟡 中 | 远程监控 | 向日葵、TeamViewer、AnyDesk、ToDesk |
| 🟡 中 | 剪贴板/输入监控 | clipboardmon、keylogger、inputmonitor |
| ⚪ 低 | 会议工具 | 腾讯会议、钉钉、飞书、Zoom、Teams |
| ⚪ 低 | 录屏 | OBS、oCam |

### v1.6 — 反作弊分析器 (独立工具)
`analyze_educoder.ps1` — 对 EduCoder 客户端的完整逆向分析：
- LNK 快捷方式解析
- Electron 应用信息提取（版本/厂商/框架）
- 关键文件枚举（app.asar、elevate.exe、educoderkey.exe、ipsec-close.bat）
- 运行进程监控 + 内存占用
- educoderkey.exe 原生反作弊二进制分析：
  - Win32 API 模式命中检测（SetWindowsHook、RegisterHotKey、BlockInput、clipboard 等 13 项）
  - VM/远程桌面检测模式
- elevate.exe 提权机制分析（Johannes Passing 开源工具）
- ipsec-close.bat 网络封锁策略分析
- app.asar Electron JS 层反作弊分析（fullScreen、globalShortcut、clipboard API 等）
- 注册表持久化检查

---

## StealthCapture.dll 编译

```bash
# 使用 .NET Framework 4.0 编译
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe \
  /target:library \
  /out:StealthCapture.dll \
  /reference:System.Drawing.dll \
  /reference:System.Windows.Forms.dll \
  StealthCapture.cs
```

DLL 导出方法：
| 方法 | 说明 |
|------|------|
| `DxgiToFile(path)` | DXGI GPU 桌面复制 → PNG |
| `GdiToFile(path)` | GDI BitBlt 回退 → PNG |
| `Shutdown()` | 释放所有全局 COM/D3D 资源 |

---

## 技术架构

```
┌─────────────────────────────────────────────┐
│                  pc_screenshot.py            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  GUI     │ │   CLI    │ │  Hotkey      │ │
│  │ tkinter  │ │  argparse│ │  GetAsyncKey │ │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
│       │            │              │          │
│  ┌────┴────────────┴──────────────┴───────┐  │
│  │         Capture Engine                │  │
│  │  ┌─────────┐  ┌──────────────────┐    │  │
│  │  │  GDI32  │  │  Stealth (PS1)   │    │  │
│  │  │ BitBlt  │  │  → DXGI / GDI    │    │  │
│  │  └─────────┘  └──────────────────┘    │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │       Anti-Cheat Scanner             │  │
│  │  Process Enum + Window Title Regex   │  │
│  └───────────────────────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │  Config  │ │  Logger  │ │   i18n     │  │
│  │  JSON    │ │  file   │ │  zh/en     │  │
│  └──────────┘ └──────────┘ └────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 安全声明

本工具仅供学习和授权测试使用。使用者需遵守当地法律法规及考试/平台的使用条款。作者不对任何滥用行为承担责任。
