# SimulateInput CLI Usage

Use this reference when driving the local SimulateInput project through the CLI instead of MCP.

## Entry Point

Run commands from the project root:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main <command> ...
```

The CLI returns JSON to stdout for normal command results.

## Common Workflow

Use this order for most UI automation tasks:

1. Run `doctor`
2. Start a session
3. List windows
4. Attach a window
5. Try `locate uia` for native controls
6. Try `locate text` for visible labels
7. Try `locate ocr` for rendered text and `locate image` for visual templates
8. Execute input actions
9. Capture screenshots for evidence

## Core Commands

### doctor

Inspect built-in profiles, MCP tools, and current driver capability.

```powershell
python -m simulateinput.cli.main doctor
```

### session start

Create a new session.

```powershell
python -m simulateinput.cli.main session start
python -m simulateinput.cli.main session start --profile privileged_lab --operator tester
```

Important fields in the result:

- `session.session_id`
- `session.profile`
- `session.platform`

### session show

Read one saved session.

```powershell
python -m simulateinput.cli.main session show <session_id>
```

### session list

List saved sessions.

```powershell
python -m simulateinput.cli.main session list
```

### case run

Run a YAML automation case file.

```powershell
python -m simulateinput.cli.main case run tests/smoke.yaml
python -m simulateinput.cli.main case run tests/smoke.yaml --operator nightly-runner
```

### window list

List visible windows for the active platform driver.

```powershell
python -m simulateinput.cli.main window list --session-id <session_id>
```

Important fields in each window:

- `window_id`
- `title`
- `bounds.x`
- `bounds.y`
- `bounds.width`
- `bounds.height`

### window attach

Attach to a target window.

Prefer `--window-id` when available.

```powershell
python -m simulateinput.cli.main window attach --session-id <session_id> --window-id <window_id>
python -m simulateinput.cli.main window attach --session-id <session_id> --title "Settings"
```

## Action Commands

All current coordinates are relative to the attached window.

## Locator Commands

### locate text

Find visible text inside the active or specified window.

```powershell
python -m simulateinput.cli.main locate text --session-id <session_id> --text "Submit"
python -m simulateinput.cli.main locate text --session-id <session_id> --text "Submit" --exact
```

### locate uia

Find UIA controls in the active or specified window.

```powershell
python -m simulateinput.cli.main locate uia --session-id <session_id> --name "Submit"
python -m simulateinput.cli.main locate uia --session-id <session_id> --automation-id submitButton --exact
python -m simulateinput.cli.main locate uia --session-id <session_id> --control-type Button
```

### locate ocr

Find OCR text in the active or specified window.

Requires local `Tesseract OCR` on `PATH`.

```powershell
python -m simulateinput.cli.main locate ocr --session-id <session_id> --text "Confirm"
python -m simulateinput.cli.main locate ocr --session-id <session_id> --text "Confirm" --confidence-threshold 0.7
```

### locate image

Find an image template in the active or specified window.

```powershell
python -m simulateinput.cli.main locate image --session-id <session_id> --image-path assets/button.png
python -m simulateinput.cli.main locate image --session-id <session_id> --image-path assets/button.png --threshold 0.95
```

### action click

```powershell
python -m simulateinput.cli.main action click --session-id <session_id> --x 100 --y 200
python -m simulateinput.cli.main action click --session-id <session_id> --x 100 --y 200 --dry-run
```

### action click-text

```powershell
python -m simulateinput.cli.main action click-text --session-id <session_id> --text "Submit"
python -m simulateinput.cli.main action click-text --session-id <session_id> --text "Submit" --exact --dry-run
```

### action click-uia

```powershell
python -m simulateinput.cli.main action click-uia --session-id <session_id> --automation-id submitButton --exact
python -m simulateinput.cli.main action click-uia --session-id <session_id> --name "Submit" --dry-run
```

### action click-ocr

Requires local `Tesseract OCR` on `PATH`.

```powershell
python -m simulateinput.cli.main action click-ocr --session-id <session_id> --text "Confirm"
python -m simulateinput.cli.main action click-ocr --session-id <session_id> --text "Confirm" --confidence-threshold 0.7 --dry-run
```

### action click-image

```powershell
python -m simulateinput.cli.main action click-image --session-id <session_id> --image-path assets/button.png
python -m simulateinput.cli.main action click-image --session-id <session_id> --image-path assets/button.png --threshold 0.95 --dry-run
```

### action drag

```powershell
python -m simulateinput.cli.main action drag --session-id <session_id> --x1 100 --y1 200 --x2 400 --y2 200 --duration-ms 800
python -m simulateinput.cli.main action drag --session-id <session_id> --x1 100 --y1 200 --x2 400 --y2 200 --dry-run
```

### action type

```powershell
python -m simulateinput.cli.main action type --session-id <session_id> --text "hello world"
python -m simulateinput.cli.main action type --session-id <session_id> --text "hello world" --dry-run
```

### action press-key

```powershell
python -m simulateinput.cli.main action press-key --session-id <session_id> --key enter
python -m simulateinput.cli.main action press-key --session-id <session_id> --key enter --dry-run
```

### action hotkey

```powershell
python -m simulateinput.cli.main action hotkey --session-id <session_id> --keys ctrl a
python -m simulateinput.cli.main action hotkey --session-id <session_id> --keys ctrl a --dry-run
```

### action clear-text

```powershell
python -m simulateinput.cli.main action clear-text --session-id <session_id>
python -m simulateinput.cli.main action clear-text --session-id <session_id> --dry-run
```

### action screenshot

Output should use `.png` or `.bmp`.

```powershell
python -m simulateinput.cli.main action screenshot --session-id <session_id> --output artifacts/shot.png
python -m simulateinput.cli.main action screenshot --session-id <session_id> --output artifacts/shot.png --dry-run
```

## MCP Helper Commands

Use these when checking or serving the local MCP layer:

```powershell
python -m simulateinput.cli.main mcp tools
python -m simulateinput.cli.main mcp serve
```

## YAML Case Runner

Supported locator-driven step actions in the current MVP:

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
- `type_text`
- `press_key`
- `hotkey`
- `clear_text`
- `screenshot`

Example:

```yaml
name: locator-smoke
profile: lab_default
steps:
  - action: attach_window
    title: SimulateInput OCR Smoke

  - action: locate_text
    text: SMOKE

  - action: click_text
    text: SMOKE

  - action: screenshot
    output: artifacts/locator-smoke.png
```

## Operating Rules

- Start with `doctor` if driver support is uncertain.
- Attach the target window before actions that should not rely on stale session state.
- Use `--dry-run` for risky coordinates.
- Capture screenshots around important checkpoints.
- Report the exact command, `session_id`, and `window_id` used.

## Maintenance Notes

- Keep this file aligned with `src/simulateinput/cli/main.py`
- Update examples when flags or subcommands change
- Add a short example for every new CLI command
