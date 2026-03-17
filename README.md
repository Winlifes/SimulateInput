# SimulateInput

English | [中文](#中文)

SimulateInput is a cross-platform desktop and browser automation platform for testing your own websites, desktop applications, installers, and system-level UI flows.

It combines direct input execution, multiple locator strategies, CLI and MCP interfaces, and YAML-driven reusable test cases so the same automation core can be used by engineers, CI pipelines, and AI agents.

## Highlights

- Cross-platform driver architecture for Windows, macOS, Linux X11, and Linux Wayland compatibility
- Multiple locator strategies:
  - structured accessibility lookup
  - visible text lookup
  - OCR-based text lookup
  - image template matching
  - coordinate fallback
- Real input actions:
  - click
  - drag
  - type text
  - press key
  - hotkey
  - clear text
  - screenshot
- MCP server for AI tool calling
- YAML case runner for repeatable automation flows
- Skill definitions and references for AI-assisted execution
- Structured `doctor` diagnostics with remediation hints for local setup issues

## Current Platform Status

- Windows: primary implementation, real execution and smoke tested
- macOS: MVP driver implemented, with structured permission diagnostics, title-plus-geometry window matching, and safer `click_uia` pre-checks
- Linux X11: MVP driver implemented, depends on `wmctrl`, `xdotool`, screenshot helpers, and optional AT-SPI tooling
- Linux Wayland: compatibility layer, helper-tool dependent and not yet full parity

## Repository Structure

- `src/simulateinput/`
  - core engine
  - platform drivers
  - locators
  - CLI
  - MCP server
  - case runner
- `docs/automation-platform-design.md`
  - architecture and implementation plan
- `docs/cross-platform-installation.md`
  - platform setup, dependencies, and permissions
- `skills/simulateinput/`
  - skill definition and CLI / MCP references
- `tests/`
  - unit tests and smoke case YAML files

## Quick Start

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main doctor
python -m simulateinput.cli.main doctor --compact
python -m simulateinput.cli.main doctor --verbose
python -m simulateinput.cli.main session start
python -m simulateinput.cli.main mcp tools
```

`doctor` output modes:

- default: built-in profiles, MCP tool names, and driver diagnostics
- `--compact`: reduced payload for UI surfaces that mainly need driver state and remediation
- `--verbose`: default payload plus full MCP tool metadata

## Typical CLI Workflow

```powershell
$env:PYTHONPATH='src'

python -m simulateinput.cli.main session start
python -m simulateinput.cli.main window list --session-id <session_id>
python -m simulateinput.cli.main window attach --session-id <session_id> --window-id <window_id>

python -m simulateinput.cli.main locate uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action click-uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action screenshot --session-id <session_id> --output artifacts/shot.png
```

On macOS, `click-uia` now validates that the chosen control is visible, enabled, and reasonably actionable before clicking its center.

## YAML Case Runner

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main case run tests/e2e/cases/windows-smoke.yaml
```

Example case:

```yaml
name: locator-smoke
profile: lab_default
steps:
  - action: attach_window
    title: Notepad

  - action: locate_text
    text: File

  - action: screenshot
    output: artifacts/locator-smoke.png
```

## MCP

Run the local MCP server:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main mcp serve
```

Current MCP capabilities include:

- session management
- window attach
- structured locators
- OCR and image locators
- click and drag actions
- keyboard actions
- screenshot capture

## Installation

See `docs/cross-platform-installation.md` for:

- Python dependencies
- Tesseract OCR setup
- macOS permissions
- Linux helper packages
- platform smoke cases

## Documentation

- Architecture: `docs/automation-platform-design.md`
- Installation: `docs/cross-platform-installation.md`
- Skill: `skills/simulateinput/SKILL.md`
- CLI reference: `skills/simulateinput/references/cli-usage.md`
- MCP reference: `skills/simulateinput/references/mcp-tools.md`

## macOS Notes

- `doctor` reports structured permission status for `Accessibility`, `Automation`, and `Screen Recording`
- remediation hints now include `system_settings_path`, `shell_hint`, and `copyable_steps`
- `find_uia` and `focus_window` use title-plus-geometry matching to reduce wrong-window selection when titles repeat
- screenshots, OCR, and image matching still require `Screen Recording`

## Safety Boundary

SimulateInput is intended for automation of your own software, test environments, and explicitly authorized systems.

It is not intended for bypassing third-party anti-bot controls, CAPTCHAs, or unrelated security mechanisms.

---

## 中文

SimulateInput 是一个跨平台的桌面与浏览器自动化测试平台，用于测试你自己的网页、桌面软件、安装器以及系统级 UI 流程。

它把真实输入执行、多种定位策略、CLI / MCP 接口和 YAML 可复用测试用例整合到同一个自动化核心中，既可以给工程师直接使用，也可以接入 CI 和 AI Agent。

## 核心能力

- 跨平台驱动架构：Windows、macOS、Linux X11，以及 Linux Wayland 兼容层
- 多种定位方式：
  - 结构化辅助功能 / 控件树定位
  - 可见文本定位
  - OCR 文本定位
  - 图像模板定位
  - 坐标兜底
- 真实输入动作：
  - 点击
  - 拖拽
  - 文本输入
  - 单键输入
  - 组合键
  - 清空文本
  - 截图
- MCP 服务，可供 AI 通过工具调用
- YAML case runner，可执行可复用的自动化测试流程
- 为 AI 使用准备的 skill 文档和参考资料
- 结构化 `doctor` 诊断输出，可直接给本地环境修复提示

## 当前平台状态

- Windows：主实现，已完成真实执行和 smoke test
- macOS：已完成 MVP 驱动，支持结构化权限诊断、基于标题加几何信息的窗口匹配，以及更安全的 `click_uia` 预检查
- Linux X11：已完成 MVP 驱动，依赖 `wmctrl`、`xdotool`、截图工具和可选 AT-SPI 环境
- Linux Wayland：当前是兼容层，依赖外部 helper，能力还未与 Windows 等价

## 仓库结构

- `src/simulateinput/`
  - 核心引擎
  - 平台驱动
  - 定位器
  - CLI
  - MCP 服务
  - 用例运行器
- `docs/automation-platform-design.md`
  - 总体设计稿
- `docs/cross-platform-installation.md`
  - 跨平台安装、依赖和权限说明
- `skills/simulateinput/`
  - AI skill 定义和 CLI / MCP 参考
- `tests/`
  - 单元测试和 smoke case YAML

## 快速开始

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main doctor
python -m simulateinput.cli.main doctor --compact
python -m simulateinput.cli.main doctor --verbose
python -m simulateinput.cli.main session start
python -m simulateinput.cli.main mcp tools
```

`doctor` 输出模式：

- 默认：内置 profile、MCP 工具名和当前 driver 诊断
- `--compact`：更适合 UI 消费的精简结果，重点保留 driver 状态和 remediation
- `--verbose`：在默认结果上附加完整 MCP 工具元数据

## 常见 CLI 流程

```powershell
$env:PYTHONPATH='src'

python -m simulateinput.cli.main session start
python -m simulateinput.cli.main window list --session-id <session_id>
python -m simulateinput.cli.main window attach --session-id <session_id> --window-id <window_id>

python -m simulateinput.cli.main locate uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action click-uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action screenshot --session-id <session_id> --output artifacts/shot.png
```

在 macOS 上，`click-uia` 现在会在点击中心点之前先检查目标控件是否可见、可用，并且是否具备合理的可操作性。

## YAML 用例执行

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main case run tests/e2e/cases/windows-smoke.yaml
```

示例：

```yaml
name: locator-smoke
profile: lab_default
steps:
  - action: attach_window
    title: Notepad

  - action: locate_text
    text: File

  - action: screenshot
    output: artifacts/locator-smoke.png
```

## MCP 接入

启动本地 MCP 服务：

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main mcp serve
```

当前 MCP 已支持：

- 会话管理
- 窗口附着
- 结构化定位
- OCR / 图像定位
- 点击与拖拽
- 键盘动作
- 截图

## 安装说明

详见 `docs/cross-platform-installation.md`，其中包含：

- Python 依赖
- Tesseract OCR 安装
- macOS 权限配置
- Linux helper 工具安装
- 平台 smoke case 说明

## 文档

- 架构设计：`docs/automation-platform-design.md`
- 安装文档：`docs/cross-platform-installation.md`
- Skill：`skills/simulateinput/SKILL.md`
- CLI 参考：`skills/simulateinput/references/cli-usage.md`
- MCP 参考：`skills/simulateinput/references/mcp-tools.md`

## macOS 说明

- `doctor` 会输出 `Accessibility`、`Automation`、`Screen Recording` 的结构化权限状态
- remediation 结果包含 `system_settings_path`、`shell_hint` 和 `copyable_steps`
- `find_uia` 和 `focus_window` 会用“标题 + 几何信息”匹配窗口，降低重名窗口误选概率
- 截图、OCR 和图像匹配仍然依赖 `Screen Recording` 权限

## 安全边界

SimulateInput 只应用于：

- 你自己的软件
- 测试环境
- 经过明确授权的系统

它不用于绕过第三方反自动化机制、验证码或无关安全控制。
