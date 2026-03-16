# SimulateInput

Cross-platform desktop and browser automation platform for testing your own websites, desktop applications, installers, and system-level UI flows.

## Features

- Window attach, focus, click, drag, type, hotkey, clear text, and screenshot actions
- Multiple locator strategies: UIA/AX/AT-SPI style lookup, visible text, OCR, image matching, and coordinate fallback
- CLI, MCP, and YAML case runner interfaces
- Windows implementation with real smoke-tested execution
- macOS MVP, Linux X11 MVP, and Linux Wayland compatibility layer
- Skill docs for AI-driven automation workflows

## Project Layout

- `src/simulateinput/` - core engine, drivers, CLI, MCP server, runner, and locators
- `docs/automation-platform-design.md` - architecture and implementation plan
- `docs/cross-platform-installation.md` - platform-specific setup and permissions
- `skills/simulateinput/` - skill definition and MCP/CLI references
- `tests/` - unit tests and smoke case YAML files

## Quick Start

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main doctor
python -m simulateinput.cli.main session start
python -m simulateinput.cli.main mcp tools
```

## Common CLI Flow

```powershell
$env:PYTHONPATH='src'

python -m simulateinput.cli.main session start
python -m simulateinput.cli.main window list --session-id <session_id>
python -m simulateinput.cli.main window attach --session-id <session_id> --window-id <window_id>

python -m simulateinput.cli.main locate uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action click-uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main action screenshot --session-id <session_id> --output artifacts/shot.png
```

## YAML Case Runner

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main case run tests/e2e/cases/windows-smoke.yaml
```

Example step types:

- `attach_window`
- `locate_text`
- `locate_uia`
- `locate_ocr`
- `locate_image`
- `click_text`
- `click_uia`
- `click_ocr`
- `click_image`
- `click`
- `drag`
- `type_text`
- `press_key`
- `hotkey`
- `clear_text`
- `screenshot`

## MCP

Run the local MCP server:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main mcp serve
```

Current MCP tools include session management, window attach, text/UIA/OCR/image lookup, click actions, keyboard actions, drag, and screenshot capture.

## Platform Status

- `Windows` - primary implementation, real execution and smoke tested
- `macOS` - MVP driver implemented, requires Accessibility / Automation / Screen Recording permissions
- `Linux X11` - MVP driver implemented, depends on `wmctrl`, `xdotool`, and a screenshot helper
- `Linux Wayland` - compatibility layer, helper-tool dependent and not full parity

## Installation Notes

See `docs/cross-platform-installation.md` for:

- Python dependencies
- Tesseract OCR setup
- macOS permissions
- Linux X11 and Wayland helper packages

## Safety Boundary

This project is intended for automation of your own software, test environments, and explicitly authorized systems. It is not intended for bypassing third-party anti-bot controls or CAPTCHAs.
