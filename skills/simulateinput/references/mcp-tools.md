# SimulateInput MCP Tools

Use this reference when driving the local SimulateInput automation platform through the MCP server in `src/simulateinput/mcp/server.py`.

## Transport

Current MVP transport is stdio with one JSON object per line.

Start the server locally:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main mcp serve
```

Supported request methods:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`

## Tool Workflow

Use this order unless the user already has an active session:

1. Call `start_session`
2. Call `list_windows`
3. Call `attach_window`
4. Call `find_uia` when native control attributes are available
5. Call `find_text` when a visible label can anchor the action
6. Call `find_ocr_text` or `find_image` when structure is not exposed
7. Call `click`, `click_text`, `click_uia`, `click_ocr`, `click_image`, `drag`, `type_text`, `press_key`, `hotkey`, `clear_text`, or `capture_window`

Prefer `dry_run: true` when validating coordinates or reviewing a risky action.

## Tool Summary

### start_session

Start a new automation session.

Arguments:

- `profile`: optional string, default `lab_default`
- `operator`: optional string, default `mcp-client`

Returns:

- `session.session_id`
- session profile and audit metadata

### list_windows

List visible windows for the active platform driver.

Arguments:

- `session_id`: required string

Returns:

- array of windows with `window_id`, `title`, `platform`, `bounds`

### attach_window

Attach to a target window and mark it as active for later actions.

Arguments:

- `session_id`: required string
- `title`: optional string
- `window_id`: optional string

Notes:

- Provide `window_id` when available
- Provide either `title` or `window_id`

### click

Click inside the active or specified window with relative coordinates.

Arguments:

- `session_id`: required string
- `x`: required integer
- `y`: required integer
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

Notes:

- Coordinates are relative to the attached window
- Without `window_id`, the active attached window is used

### find_uia

Find UIA controls inside the active or specified window.

Arguments:

- `session_id`: required string
- `window_id`: optional string
- `name`: optional string
- `control_type`: optional string
- `automation_id`: optional string
- `exact`: optional boolean, default `false`
- `max_results`: optional integer, default `20`

Current Windows MVP behavior:

- uses `pywinauto` with the `uia` backend
- searches the attached window wrapper and descendants
- supports name, control type, and automation id filters

### find_text

Find visible text targets inside the active or specified window.

Arguments:

- `session_id`: required string
- `text`: required string
- `window_id`: optional string
- `exact`: optional boolean, default `false`

Current Windows MVP behavior:

- searches the attached window and visible child windows
- returns text, bounds, and class information when available

### click_text

Click the first visible text match inside the active or specified window.

Arguments:

- `session_id`: required string
- `text`: required string
- `window_id`: optional string
- `exact`: optional boolean, default `false`
- `dry_run`: optional boolean, default `false`

Current Windows MVP behavior:

- resolves the first text match
- clicks the center of the matched bounds

### find_ocr_text

Find OCR text regions inside the active or specified window.

Arguments:

- `session_id`: required string
- `text`: required string
- `window_id`: optional string
- `exact`: optional boolean, default `false`
- `confidence_threshold`: optional number, default `0.0`

Requirements:

- local `Tesseract OCR` installed and on `PATH`

### find_image

Find an image template inside the active or specified window.

Arguments:

- `session_id`: required string
- `image_path`: required string
- `window_id`: optional string
- `threshold`: optional number, default `0.9`
- `max_results`: optional integer, default `5`

### click_uia

Click the first UIA match inside the active or specified window.

Arguments:

- `session_id`: required string
- `window_id`: optional string
- `name`: optional string
- `control_type`: optional string
- `automation_id`: optional string
- `exact`: optional boolean, default `false`
- `dry_run`: optional boolean, default `false`

### click_ocr

Click the first OCR text match inside the active or specified window.

Arguments:

- `session_id`: required string
- `text`: required string
- `window_id`: optional string
- `exact`: optional boolean, default `false`
- `confidence_threshold`: optional number, default `0.0`
- `dry_run`: optional boolean, default `false`

### click_image

Click the first image template match inside the active or specified window.

Arguments:

- `session_id`: required string
- `image_path`: required string
- `window_id`: optional string
- `threshold`: optional number, default `0.9`
- `dry_run`: optional boolean, default `false`

### drag

Drag inside the active or specified window with relative coordinates.

Arguments:

- `session_id`: required string
- `x1`: required integer
- `y1`: required integer
- `x2`: required integer
- `y2`: required integer
- `window_id`: optional string
- `duration_ms`: optional integer, default `500`
- `dry_run`: optional boolean, default `false`

### type_text

Type text into the active or specified window.

Arguments:

- `session_id`: required string
- `text`: required string
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

### press_key

Press a single key in the active or specified window.

Arguments:

- `session_id`: required string
- `key`: required string
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

Examples of supported keys in the current Windows MVP:

- letters: `a`
- digits: `1`
- named keys: `enter`, `tab`, `escape`, `delete`, `backspace`
- arrows: `left`, `right`, `up`, `down`
- modifiers: `ctrl`, `alt`, `shift`
- function keys: `f1` to `f12`

### hotkey

Press a key chord in the active or specified window.

Arguments:

- `session_id`: required string
- `keys`: required string array
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

Example:

- `["ctrl", "a"]`

### clear_text

Clear the currently focused text field in the active or specified window.

Arguments:

- `session_id`: required string
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

Current Windows MVP behavior:

- sends `Ctrl+A`
- then sends `Delete`

### capture_window

Capture a screenshot for the active or specified window.

Arguments:

- `session_id`: required string
- `output`: required string
- `window_id`: optional string
- `dry_run`: optional boolean, default `false`

Returns:

- action result data
- screenshot artifact path when executed

## Example Calls

### List tools

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

### Start a session

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"start_session","arguments":{"profile":"lab_default","operator":"tester"}}}
```

### Attach a window

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"attach_window","arguments":{"session_id":"sess-123","window_id":"656926"}}}
```

### Preview a click

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"click","arguments":{"session_id":"sess-123","x":100,"y":200,"dry_run":true}}}
```

### Find text

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"find_text","arguments":{"session_id":"sess-123","text":"Submit"}}}
```

### Find UIA control

```json
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"find_uia","arguments":{"session_id":"sess-123","automation_id":"submitButton","exact":true}}}
```

### Find OCR text

```json
{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"find_ocr_text","arguments":{"session_id":"sess-123","text":"Confirm","confidence_threshold":0.7}}}
```

### Find image

```json
{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"find_image","arguments":{"session_id":"sess-123","image_path":"assets/button.png","threshold":0.95}}}
```

### Click text

```json
{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"click_text","arguments":{"session_id":"sess-123","text":"Submit","dry_run":true}}}
```

### Click UIA control

```json
{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"click_uia","arguments":{"session_id":"sess-123","automation_id":"submitButton","exact":true,"dry_run":true}}}
```

### Click OCR text

```json
{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"click_ocr","arguments":{"session_id":"sess-123","text":"Confirm","confidence_threshold":0.7,"dry_run":true}}}
```

### Click image

```json
{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"click_image","arguments":{"session_id":"sess-123","image_path":"assets/button.png","threshold":0.95,"dry_run":true}}}
```

### Capture a screenshot

```json
{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"capture_window","arguments":{"session_id":"sess-123","output":"artifacts/shot.png"}}}
```

### Press Enter

```json
{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"press_key","arguments":{"session_id":"sess-123","key":"enter"}}}
```

### Send Ctrl+A

```json
{"jsonrpc":"2.0","id":15,"method":"tools/call","params":{"name":"hotkey","arguments":{"session_id":"sess-123","keys":["ctrl","a"]}}}
```

### Clear focused text

```json
{"jsonrpc":"2.0","id":16,"method":"tools/call","params":{"name":"clear_text","arguments":{"session_id":"sess-123"}}}
```

## Maintenance Notes

- Keep this file aligned with `src/simulateinput/mcp/server.py`
- Update argument names when tool schemas change
- Add examples for every new MCP tool added to the server
