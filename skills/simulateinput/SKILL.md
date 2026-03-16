---
name: simulateinput
description: Control the local SimulateInput automation platform for testing your own websites, desktop software, installers, system dialogs, and other UI flows through session management, window attachment, clicking, dragging, typing, and screenshots. Use when Codex needs to drive the SimulateInput project via MCP or CLI, inspect available windows, attach to a target window, execute or preview input actions, capture evidence, or help extend the platform itself.
---

# SimulateInput

## Overview

Use this skill to operate the local `SimulateInput` project as a reusable automation layer.
Prefer the MCP server when tool-style calling is available; otherwise use the CLI in this repo.
Use the YAML case runner when the task is a repeatable scripted flow rather than an interactive one-off action.

## Workflow

1. Check capability before acting.
2. Start or reuse a session.
3. List windows and attach to the correct target.
4. Prefer exact window ids over fuzzy titles when possible.
5. Prefer `find_uia` or `click_uia` for standard native controls when attributes are available.
6. Prefer `find_text` or `click_text` for visible labels before falling back to OCR or raw coordinates.
7. Use `find_ocr_text` or `click_ocr` for rendered text that is not exposed through UIA or window text.
8. Use `find_image` or `click_image` for iconography, canvas content, or custom-painted controls.
9. Use relative window coordinates only when structured locators are unavailable.
10. Capture screenshots before or after important steps.
11. Return structured results, artifact paths, and any follow-up risk.

## Preferred Interfaces

### MCP

Use MCP first for AI-driven execution. Current tool names live in `src/simulateinput/mcp/server.py`.
For request/response patterns and current MVP tool arguments, read `references/mcp-tools.md`.

Current MVP tools:

- `start_session`
- `list_windows`
- `attach_window`
- `find_text`
- `find_uia`
- `find_ocr_text`
- `find_image`
- `click`
- `click_text`
- `click_uia`
- `click_ocr`
- `click_image`
- `drag`
- `type_text`
- `press_key`
- `hotkey`
- `clear_text`
- `capture_window`

Current CLI case runner:

- `python -m simulateinput.cli.main case run <path-to-yaml>`

### CLI

Use the CLI when MCP is unavailable or when debugging locally.
Primary entrypoint: `python -m simulateinput.cli.main`
For command patterns and expected outputs, read `references/cli-usage.md`.

Common commands:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main doctor
python -m simulateinput.cli.main session start
python -m simulateinput.cli.main window list --session-id <id>
python -m simulateinput.cli.main window attach --session-id <id> --window-id <window_id>
python -m simulateinput.cli.main action click --session-id <id> --x 100 --y 200
python -m simulateinput.cli.main action drag --session-id <id> --x1 100 --y1 200 --x2 400 --y2 200 --duration-ms 800
python -m simulateinput.cli.main action type --session-id <id> --text "hello"
python -m simulateinput.cli.main action screenshot --session-id <id> --output artifacts/shot.png
python -m simulateinput.cli.main mcp tools
python -m simulateinput.cli.main mcp serve
```

## Action Rules

- Treat coordinates as relative to the attached window unless the tool explicitly says otherwise.
- Prefer `find_uia` and `click_uia` for native controls in the current Windows MVP.
- Prefer `find_text` and `click_text` for visible labels exposed through window text.
- Prefer `find_ocr_text` and `click_ocr` for rendered text not exposed through UIA.
- Prefer `find_image` and `click_image` for icons and custom visuals.
- Prefer the YAML case runner for repeatable multi-step flows that should be stored as test assets.
- Attach to the target window before executing destructive or high-impact actions.
- Use `--dry-run` or the MCP `dry_run` flag when you need to preview coordinates or confirm intent.
- Prefer screenshot capture around critical checkpoints so the user gets evidence.
- Report the exact window title and `window_id` you acted on.
- If OCR is needed, ensure `Tesseract OCR` is installed and available on `PATH`.

## Profiles

Use the least permissive profile that still fits the task.

- `standard`: ordinary application testing
- `lab_default`: default test-lab profile
- `privileged_lab`: system-level test flows, sensitive windows, and destructive lab actions

If the task clearly involves system settings, installers, privileged dialogs, or other lab-only surfaces, choose `privileged_lab`.

## Extension Guidance

When extending the platform, inspect these files first:

- `src/simulateinput/core/engine.py`
- `src/simulateinput/drivers/windows/__init__.py`
- `src/simulateinput/drivers/macos/__init__.py`
- `src/simulateinput/drivers/linux_x11/__init__.py`
- `src/simulateinput/drivers/linux_wayland/__init__.py`
- `src/simulateinput/mcp/server.py`
- `src/simulateinput/cli/main.py`
- `docs/automation-platform-design.md`
- `docs/cross-platform-installation.md`

If the change affects MCP behavior or tool schemas, update `references/mcp-tools.md` in the same change.
If the change affects CLI commands or flags, update `references/cli-usage.md` in the same change.

Keep CLI, MCP, and engine behavior aligned. Add tests under `tests/unit/` for any new tool, action, or engine path.

## Boundaries

- Use this skill for automation of the user's own software, test environments, or explicitly authorized systems.
- Do not use this skill to bypass third-party anti-bot checks, CAPTCHAs, or unrelated security controls.
