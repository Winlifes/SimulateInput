from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulateinput import __version__
from simulateinput.core.engine import AutomationEngine
from simulateinput.core.errors import DriverNotAvailableError, SessionNotFoundError, SimulateInputError
from simulateinput.core.policy import BUILTIN_PROFILES
from simulateinput.core.session import SessionStore
from simulateinput.mcp.server import MCPServer, list_tools
from simulateinput.runner.case_runner import load_case, run_case


def emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simctl", description="Cross-platform automation test platform.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the current package version.")
    doctor_parser = subparsers.add_parser("doctor", help="Show built-in profiles, driver diagnostics, and MCP tool names.")
    doctor_mode = doctor_parser.add_mutually_exclusive_group()
    doctor_mode.add_argument("--compact", action="store_true", help="Emit a reduced payload focused on driver status and remediation.")
    doctor_mode.add_argument("--verbose", action="store_true", help="Emit expanded driver details plus full MCP tool metadata.")

    session_parser = subparsers.add_parser("session", help="Manage automation sessions.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    session_start = session_subparsers.add_parser("start", help="Start a new session.")
    session_start.add_argument("--profile", default="lab_default")
    session_start.add_argument("--operator", default="local-user")
    session_start.add_argument("--state-root", type=Path)

    session_show = session_subparsers.add_parser("show", help="Show one session.")
    session_show.add_argument("session_id")
    session_show.add_argument("--state-root", type=Path)

    session_list = session_subparsers.add_parser("list", help="List stored sessions.")
    session_list.add_argument("--state-root", type=Path)

    window_parser = subparsers.add_parser("window", help="Inspect and attach desktop windows.")
    window_subparsers = window_parser.add_subparsers(dest="window_command", required=True)

    window_list = window_subparsers.add_parser("list", help="List visible windows.")
    window_list.add_argument("--session-id", required=True)
    window_list.add_argument("--state-root", type=Path)

    window_attach = window_subparsers.add_parser("attach", help="Attach to a window by title or id.")
    window_attach.add_argument("--session-id", required=True)
    window_attach.add_argument("--title")
    window_attach.add_argument("--window-id")
    window_attach.add_argument("--state-root", type=Path)

    locate_parser = subparsers.add_parser("locate", help="Resolve text or control targets inside a window.")
    locate_subparsers = locate_parser.add_subparsers(dest="locate_command", required=True)

    locate_text = locate_subparsers.add_parser("text", help="Find visible text inside the active or specified window.")
    locate_text.add_argument("--session-id", required=True)
    locate_text.add_argument("--window-id")
    locate_text.add_argument("--text", required=True)
    locate_text.add_argument("--exact", action="store_true")
    locate_text.add_argument("--state-root", type=Path)

    locate_uia = locate_subparsers.add_parser("uia", help="Find UIA controls inside the active or specified window.")
    locate_uia.add_argument("--session-id", required=True)
    locate_uia.add_argument("--window-id")
    locate_uia.add_argument("--name")
    locate_uia.add_argument("--control-type")
    locate_uia.add_argument("--automation-id")
    locate_uia.add_argument("--exact", action="store_true")
    locate_uia.add_argument("--max-results", type=int, default=20)
    locate_uia.add_argument("--state-root", type=Path)

    locate_ocr = locate_subparsers.add_parser("ocr", help="Find OCR text inside the active or specified window.")
    locate_ocr.add_argument("--session-id", required=True)
    locate_ocr.add_argument("--window-id")
    locate_ocr.add_argument("--text", required=True)
    locate_ocr.add_argument("--exact", action="store_true")
    locate_ocr.add_argument("--confidence-threshold", type=float, default=0.0)
    locate_ocr.add_argument("--state-root", type=Path)

    locate_image = locate_subparsers.add_parser("image", help="Find an image template inside the active or specified window.")
    locate_image.add_argument("--session-id", required=True)
    locate_image.add_argument("--window-id")
    locate_image.add_argument("--image-path", required=True)
    locate_image.add_argument("--threshold", type=float, default=0.9)
    locate_image.add_argument("--max-results", type=int, default=5)
    locate_image.add_argument("--state-root", type=Path)

    action_parser = subparsers.add_parser("action", help="Preview or run actions against an attached window.")
    action_subparsers = action_parser.add_subparsers(dest="action_command", required=True)

    action_click = action_subparsers.add_parser("click", help="Preview a click action.")
    action_click.add_argument("--session-id", required=True)
    action_click.add_argument("--window-id")
    action_click.add_argument("--x", type=int, required=True)
    action_click.add_argument("--y", type=int, required=True)
    action_click.add_argument("--dry-run", action="store_true")
    action_click.add_argument("--state-root", type=Path)

    action_click_text = action_subparsers.add_parser("click-text", help="Click the first text match in the active or specified window.")
    action_click_text.add_argument("--session-id", required=True)
    action_click_text.add_argument("--window-id")
    action_click_text.add_argument("--text", required=True)
    action_click_text.add_argument("--exact", action="store_true")
    action_click_text.add_argument("--dry-run", action="store_true")
    action_click_text.add_argument("--state-root", type=Path)

    action_click_uia = action_subparsers.add_parser("click-uia", help="Click the first matching UIA control.")
    action_click_uia.add_argument("--session-id", required=True)
    action_click_uia.add_argument("--window-id")
    action_click_uia.add_argument("--name")
    action_click_uia.add_argument("--control-type")
    action_click_uia.add_argument("--automation-id")
    action_click_uia.add_argument("--exact", action="store_true")
    action_click_uia.add_argument("--dry-run", action="store_true")
    action_click_uia.add_argument("--state-root", type=Path)

    action_click_ocr = action_subparsers.add_parser("click-ocr", help="Click the first matching OCR text region.")
    action_click_ocr.add_argument("--session-id", required=True)
    action_click_ocr.add_argument("--window-id")
    action_click_ocr.add_argument("--text", required=True)
    action_click_ocr.add_argument("--exact", action="store_true")
    action_click_ocr.add_argument("--confidence-threshold", type=float, default=0.0)
    action_click_ocr.add_argument("--dry-run", action="store_true")
    action_click_ocr.add_argument("--state-root", type=Path)

    action_click_image = action_subparsers.add_parser("click-image", help="Click the first matching image template.")
    action_click_image.add_argument("--session-id", required=True)
    action_click_image.add_argument("--window-id")
    action_click_image.add_argument("--image-path", required=True)
    action_click_image.add_argument("--threshold", type=float, default=0.9)
    action_click_image.add_argument("--dry-run", action="store_true")
    action_click_image.add_argument("--state-root", type=Path)

    action_drag = action_subparsers.add_parser("drag", help="Preview a drag action.")
    action_drag.add_argument("--session-id", required=True)
    action_drag.add_argument("--window-id")
    action_drag.add_argument("--x1", type=int, required=True)
    action_drag.add_argument("--y1", type=int, required=True)
    action_drag.add_argument("--x2", type=int, required=True)
    action_drag.add_argument("--y2", type=int, required=True)
    action_drag.add_argument("--duration-ms", type=int, default=500)
    action_drag.add_argument("--dry-run", action="store_true")
    action_drag.add_argument("--state-root", type=Path)

    action_type = action_subparsers.add_parser("type", help="Preview text input.")
    action_type.add_argument("--session-id", required=True)
    action_type.add_argument("--window-id")
    action_type.add_argument("--text", required=True)
    action_type.add_argument("--dry-run", action="store_true")
    action_type.add_argument("--state-root", type=Path)

    action_press_key = action_subparsers.add_parser("press-key", help="Press a single key.")
    action_press_key.add_argument("--session-id", required=True)
    action_press_key.add_argument("--window-id")
    action_press_key.add_argument("--key", required=True)
    action_press_key.add_argument("--dry-run", action="store_true")
    action_press_key.add_argument("--state-root", type=Path)

    action_hotkey = action_subparsers.add_parser("hotkey", help="Press a key chord in order.")
    action_hotkey.add_argument("--session-id", required=True)
    action_hotkey.add_argument("--window-id")
    action_hotkey.add_argument("--keys", nargs="+", required=True)
    action_hotkey.add_argument("--dry-run", action="store_true")
    action_hotkey.add_argument("--state-root", type=Path)

    action_clear_text = action_subparsers.add_parser("clear-text", help="Clear the currently focused text field.")
    action_clear_text.add_argument("--session-id", required=True)
    action_clear_text.add_argument("--window-id")
    action_clear_text.add_argument("--dry-run", action="store_true")
    action_clear_text.add_argument("--state-root", type=Path)

    action_screenshot = action_subparsers.add_parser("screenshot", help="Preview screenshot output.")
    action_screenshot.add_argument("--session-id", required=True)
    action_screenshot.add_argument("--window-id")
    action_screenshot.add_argument("--output", required=True)
    action_screenshot.add_argument("--dry-run", action="store_true")
    action_screenshot.add_argument("--state-root", type=Path)

    mcp_parser = subparsers.add_parser("mcp", help="Inspect or run the MCP server.")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", required=True)

    mcp_subparsers.add_parser("tools", help="List exposed MCP tools.")

    mcp_serve = mcp_subparsers.add_parser("serve", help="Run the stdio MCP server loop.")
    mcp_serve.add_argument("--state-root", type=Path)

    case_parser = subparsers.add_parser("case", help="Inspect and run YAML case files.")
    case_subparsers = case_parser.add_subparsers(dest="case_command", required=True)

    case_validate = case_subparsers.add_parser("validate", help="Validate a YAML case file.")
    case_validate.add_argument("path", type=Path)

    case_run = case_subparsers.add_parser("run", help="Run a YAML case file.")
    case_run.add_argument("path", type=Path)
    case_run.add_argument("--operator", default="cli-case-runner")
    case_run.add_argument("--state-root", type=Path)

    return parser


def resolve_store(state_root: Path | None) -> SessionStore:
    return SessionStore(root=(state_root / "sessions") if state_root else None)


def resolve_engine(state_root: Path | None) -> AutomationEngine:
    return AutomationEngine(state_root=state_root)


def build_doctor_payload(engine: AutomationEngine, compact: bool = False, verbose: bool = False) -> dict:
    driver = engine.probe_driver()
    tool_defs = list_tools()
    if compact:
        return {
            "ok": True,
            "driver": {
                "available": driver["available"],
                "platform": driver["platform"],
                "message": driver["message"],
                "capabilities": driver["capabilities"],
                "remediation": driver.get("details", {}).get("remediation", []),
            },
        }
    payload = {
        "ok": True,
        "profiles": sorted(BUILTIN_PROFILES),
        "mcp_tools": [tool.name for tool in tool_defs],
        "driver": driver,
    }
    if verbose:
        payload["version"] = __version__
        payload["mcp_tool_details"] = [tool.to_dict() for tool in tool_defs]
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)

        if args.command == "version":
            emit({"ok": True, "version": __version__})
            return 0

        if args.command == "doctor":
            engine = resolve_engine(None)
            emit(build_doctor_payload(engine, compact=getattr(args, "compact", False), verbose=getattr(args, "verbose", False)))
            return 0

        if args.command == "mcp":
            if args.mcp_command == "tools":
                emit({"ok": True, "tools": [tool.to_dict() for tool in list_tools()]})
                return 0
            if args.mcp_command == "serve":
                server = MCPServer(state_root=getattr(args, "state_root", None))
                return server.serve()

        if args.command == "session":
            store = resolve_store(getattr(args, "state_root", None))
            if args.session_command == "start":
                session = store.start(profile_name=args.profile, operator=args.operator)
                emit({"ok": True, "session": session.to_dict()})
                return 0
            if args.session_command == "show":
                session = store.get(args.session_id)
                emit({"ok": True, "session": session.to_dict()})
                return 0
            if args.session_command == "list":
                emit({"ok": True, "sessions": [session.to_dict() for session in store.list()]})
                return 0

        if args.command == "window":
            engine = resolve_engine(getattr(args, "state_root", None))
            if args.window_command == "list":
                windows = engine.list_windows(args.session_id)
                emit({"ok": True, "windows": [window.to_dict() for window in windows]})
                return 0
            if args.window_command == "attach":
                if not args.title and not args.window_id:
                    parser.error("window attach requires --title or --window-id")
                window = engine.attach_window(
                    session_id=args.session_id,
                    title=args.title,
                    window_id=args.window_id,
                )
                emit({"ok": True, "window": window.to_dict()})
                return 0

        if args.command == "locate":
            engine = resolve_engine(getattr(args, "state_root", None))
            if args.locate_command == "text":
                matches = engine.find_text(
                    session_id=args.session_id,
                    text=args.text,
                    window_id=args.window_id,
                    exact=args.exact,
                )
                emit({"ok": True, "matches": [match.to_dict() for match in matches]})
                return 0
            if args.locate_command == "uia":
                matches = engine.find_uia(
                    session_id=args.session_id,
                    window_id=args.window_id,
                    name=args.name,
                    control_type=args.control_type,
                    automation_id=args.automation_id,
                    exact=args.exact,
                    max_results=args.max_results,
                )
                emit({"ok": True, "matches": [match.to_dict() for match in matches]})
                return 0
            if args.locate_command == "ocr":
                matches = engine.find_ocr_text(
                    session_id=args.session_id,
                    text=args.text,
                    window_id=args.window_id,
                    exact=args.exact,
                    confidence_threshold=args.confidence_threshold,
                )
                emit({"ok": True, "matches": [match.to_dict() for match in matches]})
                return 0
            if args.locate_command == "image":
                matches = engine.find_image(
                    session_id=args.session_id,
                    image_path=args.image_path,
                    window_id=args.window_id,
                    threshold=args.threshold,
                    max_results=args.max_results,
                )
                emit({"ok": True, "matches": [match.to_dict() for match in matches]})
                return 0

        if args.command == "action":
            engine = resolve_engine(getattr(args, "state_root", None))
            if args.action_command == "click":
                result = (
                    engine.preview_click(
                        session_id=args.session_id,
                        x=args.x,
                        y=args.y,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_click(
                        session_id=args.session_id,
                        x=args.x,
                        y=args.y,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "click-text":
                result = (
                    engine.preview_click_text(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                        exact=args.exact,
                    )
                    if args.dry_run
                    else engine.execute_click_text(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                        exact=args.exact,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "click-uia":
                result = (
                    engine.preview_click_uia(
                        session_id=args.session_id,
                        window_id=args.window_id,
                        name=args.name,
                        control_type=args.control_type,
                        automation_id=args.automation_id,
                        exact=args.exact,
                    )
                    if args.dry_run
                    else engine.execute_click_uia(
                        session_id=args.session_id,
                        window_id=args.window_id,
                        name=args.name,
                        control_type=args.control_type,
                        automation_id=args.automation_id,
                        exact=args.exact,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "click-ocr":
                result = (
                    engine.preview_click_ocr(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                        exact=args.exact,
                        confidence_threshold=args.confidence_threshold,
                    )
                    if args.dry_run
                    else engine.execute_click_ocr(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                        exact=args.exact,
                        confidence_threshold=args.confidence_threshold,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "click-image":
                result = (
                    engine.preview_click_image(
                        session_id=args.session_id,
                        image_path=args.image_path,
                        window_id=args.window_id,
                        threshold=args.threshold,
                    )
                    if args.dry_run
                    else engine.execute_click_image(
                        session_id=args.session_id,
                        image_path=args.image_path,
                        window_id=args.window_id,
                        threshold=args.threshold,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "drag":
                result = (
                    engine.preview_drag(
                        session_id=args.session_id,
                        x1=args.x1,
                        y1=args.y1,
                        x2=args.x2,
                        y2=args.y2,
                        duration_ms=args.duration_ms,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_drag(
                        session_id=args.session_id,
                        x1=args.x1,
                        y1=args.y1,
                        x2=args.x2,
                        y2=args.y2,
                        duration_ms=args.duration_ms,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "type":
                result = (
                    engine.preview_type_text(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_type_text(
                        session_id=args.session_id,
                        text=args.text,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "press-key":
                result = (
                    engine.preview_press_key(
                        session_id=args.session_id,
                        key=args.key,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_press_key(
                        session_id=args.session_id,
                        key=args.key,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "hotkey":
                result = (
                    engine.preview_hotkey(
                        session_id=args.session_id,
                        keys=args.keys,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_hotkey(
                        session_id=args.session_id,
                        keys=args.keys,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "clear-text":
                result = (
                    engine.preview_clear_text(
                        session_id=args.session_id,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_clear_text(
                        session_id=args.session_id,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0
            if args.action_command == "screenshot":
                result = (
                    engine.preview_screenshot(
                        session_id=args.session_id,
                        output=args.output,
                        window_id=args.window_id,
                    )
                    if args.dry_run
                    else engine.execute_screenshot(
                        session_id=args.session_id,
                        output=args.output,
                        window_id=args.window_id,
                    )
                )
                emit(result.to_dict())
                return 0

        if args.command == "case" and args.case_command == "validate":
            case_def = load_case(args.path)
            emit(
                {
                    "ok": True,
                    "case": {
                        "name": case_def.name,
                        "profile": case_def.profile,
                        "step_count": len(case_def.steps),
                    },
                }
            )
            return 0
        if args.command == "case" and args.case_command == "run":
            engine = resolve_engine(getattr(args, "state_root", None))
            report = run_case(args.path, engine=engine, operator=args.operator)
            emit({"ok": True, "case": report})
            return 0

        parser.error("unsupported command")
        return 2
    except (DriverNotAvailableError, SessionNotFoundError, SimulateInputError, ValueError) as exc:
        emit({"ok": False, "code": exc.__class__.__name__, "message": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
