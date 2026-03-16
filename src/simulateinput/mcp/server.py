from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from simulateinput import __version__
from simulateinput.core.engine import AutomationEngine
from simulateinput.core.models import ActionResult

JsonDict = dict[str, Any]


@dataclass(frozen=True, slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: JsonDict

    def to_dict(self) -> JsonDict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


ToolHandler = Callable[[JsonDict], JsonDict]


class MCPServer:
    def __init__(self, engine: AutomationEngine | None = None, state_root: Path | None = None) -> None:
        self.engine = engine or AutomationEngine(state_root=state_root)
        self.tools = self._build_tools()
        self.handlers: dict[str, ToolHandler] = {
            "start_session": self._start_session,
            "list_windows": self._list_windows,
            "attach_window": self._attach_window,
            "find_text": self._find_text,
            "find_uia": self._find_uia,
            "find_ocr_text": self._find_ocr_text,
            "find_image": self._find_image,
            "click": self._click,
            "click_text": self._click_text,
            "click_uia": self._click_uia,
            "click_ocr": self._click_ocr,
            "click_image": self._click_image,
            "drag": self._drag,
            "type_text": self._type_text,
            "press_key": self._press_key,
            "hotkey": self._hotkey,
            "clear_text": self._clear_text,
            "capture_window": self._capture_window,
        }

    def _build_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                "start_session",
                "Start an automation session with a named profile.",
                {
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string", "default": "lab_default"},
                        "operator": {"type": "string", "default": "mcp-client"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "list_windows",
                "List visible windows for the current platform driver.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "attach_window",
                "Attach to a window by title or explicit window id.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "title": {"type": "string"},
                        "window_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "find_text",
                "Find visible text targets inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "text": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "text"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "find_uia",
                "Find UIA controls inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "name": {"type": "string"},
                        "control_type": {"type": "string"},
                        "automation_id": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                        "max_results": {"type": "integer", "default": 20},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "find_ocr_text",
                "Find OCR text regions inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "text": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                        "confidence_threshold": {"type": "number", "default": 0.0},
                    },
                    "required": ["session_id", "text"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "find_image",
                "Find an image template inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "image_path": {"type": "string"},
                        "threshold": {"type": "number", "default": 0.9},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["session_id", "image_path"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "click",
                "Click inside the active or specified window using relative coordinates.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "x", "y"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "click_text",
                "Click the first text match inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "text": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "text"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "click_uia",
                "Click the first UIA match inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "name": {"type": "string"},
                        "control_type": {"type": "string"},
                        "automation_id": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "click_ocr",
                "Click the first OCR text match inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "text": {"type": "string"},
                        "exact": {"type": "boolean", "default": False},
                        "confidence_threshold": {"type": "number", "default": 0.0},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "text"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "click_image",
                "Click the first image template match inside the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "image_path": {"type": "string"},
                        "threshold": {"type": "number", "default": 0.9},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "image_path"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "drag",
                "Drag inside the active or specified window using relative coordinates.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "x1": {"type": "integer"},
                        "y1": {"type": "integer"},
                        "x2": {"type": "integer"},
                        "y2": {"type": "integer"},
                        "duration_ms": {"type": "integer", "default": 500},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "x1", "y1", "x2", "y2"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "type_text",
                "Type text into the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "text": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "text"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "press_key",
                "Press a single key in the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "key": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "key"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "hotkey",
                "Press a key chord in the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "keys": {"type": "array", "items": {"type": "string"}},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "keys"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "clear_text",
                "Clear the currently focused text field in the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                "capture_window",
                "Capture a screenshot for the active or specified window.",
                {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "window_id": {"type": "string"},
                        "output": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id", "output"],
                    "additionalProperties": False,
                },
            ),
        ]

    def list_tools(self) -> list[MCPTool]:
        return self.tools

    def call_tool(self, name: str, arguments: JsonDict | None = None) -> JsonDict:
        if name not in self.handlers:
            raise ValueError(f"unknown tool: {name}")
        return self.handlers[name](arguments or {})

    def handle_request(self, request: JsonDict) -> JsonDict:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "mvp",
                    "serverInfo": {"name": "simulateinput", "version": __version__},
                    "capabilities": {"tools": {}},
                }
            elif method == "ping":
                result = {"ok": True}
            elif method == "tools/list":
                result = {"tools": [tool.to_dict() for tool in self.list_tools()]}
            elif method == "tools/call":
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            else:
                return self._error_response(request_id, -32601, f"method not found: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return self._error_response(request_id, -32000, str(exc))

    def serve(self, input_stream=None, output_stream=None) -> int:
        source = input_stream or sys.stdin
        sink = output_stream or sys.stdout
        for raw_line in source:
            line = raw_line.strip()
            if not line:
                continue
            response = self.handle_request(json.loads(line))
            sink.write(json.dumps(response) + "\n")
            sink.flush()
        return 0

    def _start_session(self, arguments: JsonDict) -> JsonDict:
        session = self.engine.sessions.start(
            profile_name=str(arguments.get("profile", "lab_default")),
            operator=str(arguments.get("operator", "mcp-client")),
        )
        return {"session": session.to_dict()}

    def _list_windows(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        windows = self.engine.list_windows(session_id)
        return {"windows": [window.to_dict() for window in windows]}

    def _attach_window(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        title = arguments.get("title")
        window_id = arguments.get("window_id")
        if title is None and window_id is None:
            raise ValueError("attach_window requires title or window_id")
        window = self.engine.attach_window(session_id, title=title, window_id=window_id)
        return {"window": window.to_dict()}

    def _click(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        x = int(self._require(arguments, "x"))
        y = int(self._require(arguments, "y"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_click(session_id, x, y, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_click(session_id, x, y, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _find_text(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        text = str(self._require(arguments, "text"))
        exact = bool(arguments.get("exact", False))
        matches = self.engine.find_text(session_id, text, window_id=arguments.get("window_id"), exact=exact)
        return {"matches": [match.to_dict() for match in matches]}

    def _find_uia(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        matches = self.engine.find_uia(
            session_id,
            window_id=arguments.get("window_id"),
            name=arguments.get("name"),
            control_type=arguments.get("control_type"),
            automation_id=arguments.get("automation_id"),
            exact=bool(arguments.get("exact", False)),
            max_results=int(arguments.get("max_results", 20)),
        )
        return {"matches": [match.to_dict() for match in matches]}

    def _find_ocr_text(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        text = str(self._require(arguments, "text"))
        matches = self.engine.find_ocr_text(
            session_id,
            text,
            window_id=arguments.get("window_id"),
            exact=bool(arguments.get("exact", False)),
            confidence_threshold=float(arguments.get("confidence_threshold", 0.0)),
        )
        return {"matches": [match.to_dict() for match in matches]}

    def _find_image(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        image_path = str(self._require(arguments, "image_path"))
        matches = self.engine.find_image(
            session_id,
            image_path,
            window_id=arguments.get("window_id"),
            threshold=float(arguments.get("threshold", 0.9)),
            max_results=int(arguments.get("max_results", 5)),
        )
        return {"matches": [match.to_dict() for match in matches]}

    def _click_text(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        text = str(self._require(arguments, "text"))
        exact = bool(arguments.get("exact", False))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_click_text(session_id, text, window_id=arguments.get("window_id"), exact=exact)
            if dry_run
            else self.engine.execute_click_text(session_id, text, window_id=arguments.get("window_id"), exact=exact)
        )
        return self._result_payload(result)

    def _click_uia(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_click_uia(
                session_id,
                window_id=arguments.get("window_id"),
                name=arguments.get("name"),
                control_type=arguments.get("control_type"),
                automation_id=arguments.get("automation_id"),
                exact=bool(arguments.get("exact", False)),
            )
            if dry_run
            else self.engine.execute_click_uia(
                session_id,
                window_id=arguments.get("window_id"),
                name=arguments.get("name"),
                control_type=arguments.get("control_type"),
                automation_id=arguments.get("automation_id"),
                exact=bool(arguments.get("exact", False)),
            )
        )
        return self._result_payload(result)

    def _click_ocr(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        text = str(self._require(arguments, "text"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_click_ocr(
                session_id,
                text,
                window_id=arguments.get("window_id"),
                exact=bool(arguments.get("exact", False)),
                confidence_threshold=float(arguments.get("confidence_threshold", 0.0)),
            )
            if dry_run
            else self.engine.execute_click_ocr(
                session_id,
                text,
                window_id=arguments.get("window_id"),
                exact=bool(arguments.get("exact", False)),
                confidence_threshold=float(arguments.get("confidence_threshold", 0.0)),
            )
        )
        return self._result_payload(result)

    def _click_image(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        image_path = str(self._require(arguments, "image_path"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_click_image(
                session_id,
                image_path,
                window_id=arguments.get("window_id"),
                threshold=float(arguments.get("threshold", 0.9)),
            )
            if dry_run
            else self.engine.execute_click_image(
                session_id,
                image_path,
                window_id=arguments.get("window_id"),
                threshold=float(arguments.get("threshold", 0.9)),
            )
        )
        return self._result_payload(result)

    def _drag(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        x1 = int(self._require(arguments, "x1"))
        y1 = int(self._require(arguments, "y1"))
        x2 = int(self._require(arguments, "x2"))
        y2 = int(self._require(arguments, "y2"))
        duration_ms = int(arguments.get("duration_ms", 500))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_drag(session_id, x1, y1, x2, y2, duration_ms, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_drag(session_id, x1, y1, x2, y2, duration_ms, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _type_text(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        text = str(self._require(arguments, "text"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_type_text(session_id, text, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_type_text(session_id, text, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _capture_window(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        output = str(self._require(arguments, "output"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_screenshot(session_id, output, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_screenshot(session_id, output, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _press_key(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        key = str(self._require(arguments, "key"))
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_press_key(session_id, key, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_press_key(session_id, key, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _hotkey(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        keys = arguments.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("hotkey requires a non-empty keys array")
        normalized = [str(key) for key in keys]
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_hotkey(session_id, normalized, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_hotkey(session_id, normalized, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _clear_text(self, arguments: JsonDict) -> JsonDict:
        session_id = self._require(arguments, "session_id")
        dry_run = bool(arguments.get("dry_run", False))
        result = (
            self.engine.preview_clear_text(session_id, window_id=arguments.get("window_id"))
            if dry_run
            else self.engine.execute_clear_text(session_id, window_id=arguments.get("window_id"))
        )
        return self._result_payload(result)

    def _result_payload(self, result: ActionResult) -> JsonDict:
        return result.to_dict()

    def _require(self, arguments: JsonDict, key: str) -> Any:
        if key not in arguments:
            raise ValueError(f"missing required argument: {key}")
        return arguments[key]

    def _error_response(self, request_id: Any, code: int, message: str) -> JsonDict:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def list_tools() -> list[MCPTool]:
    return MCPServer().list_tools()
