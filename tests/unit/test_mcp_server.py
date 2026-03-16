import io
import json
import tempfile
import unittest
from pathlib import Path

from simulateinput.core.engine import AutomationEngine
from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo
from simulateinput.mcp.server import MCPServer


class FakeDriver:
    platform = PlatformKind.WINDOWS

    def __init__(self) -> None:
        self.window = WindowInfo(
            window_id="win-1",
            title="Demo Window",
            platform=self.platform,
            bounds=Bounds(x=100, y=200, width=800, height=600),
        )
        self.click_calls: list[tuple[int, int]] = []
        self.key_calls: list[str] = []
        self.hotkey_calls: list[list[str]] = []
        self.clear_text_calls = 0
        self.screenshot_calls: list[tuple[str, str]] = []
        self.text_matches = [
            ElementInfo(
                element_id="child-1",
                window_id="win-1",
                platform=self.platform,
                text="Submit",
                bounds=Bounds(x=140, y=260, width=120, height=40),
                class_name="Button",
                control_type="win32-child",
                source="win32-text",
                confidence=0.9,
            )
        ]
        self.uia_matches = [
            ElementInfo(
                element_id="uia-1",
                window_id="win-1",
                platform=self.platform,
                text="Submit",
                bounds=Bounds(x=300, y=320, width=100, height=32),
                class_name="Button",
                control_type="Button",
                automation_id="submitButton",
                source="uia",
                confidence=0.98,
            )
        ]
        self.ocr_matches = [
            ElementInfo(
                element_id="ocr-1",
                window_id="win-1",
                platform=self.platform,
                text="Confirm",
                bounds=Bounds(x=410, y=360, width=90, height=28),
                control_type="ocr-text",
                source="ocr",
                confidence=0.91,
            )
        ]
        self.image_matches = [
            ElementInfo(
                element_id="img-1",
                window_id="win-1",
                platform=self.platform,
                text="button.png",
                bounds=Bounds(x=520, y=400, width=40, height=20),
                control_type="image-template",
                source="image",
                confidence=0.97,
            )
        ]

    def probe(self):
        class Probe:
            available = True
            platform = PlatformKind.WINDOWS
            message = "ok"
            capabilities = [
                "list_windows",
                "attach_window",
                "find_text",
                "find_uia",
                "find_ocr_text",
                "find_image",
                "click",
                "screenshot",
            ]

        return Probe()

    def list_windows(self) -> list[WindowInfo]:
        return [self.window]

    def focus_window(self, window_id: str) -> bool:
        return True

    def click(self, x: int, y: int) -> None:
        self.click_calls.append((x, y))

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        return None

    def type_text(self, text: str) -> None:
        return None

    def press_key(self, key: str) -> None:
        self.key_calls.append(key)

    def hotkey(self, keys: list[str]) -> None:
        self.hotkey_calls.append(keys)

    def clear_text(self) -> None:
        self.clear_text_calls += 1

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list[ElementInfo]:
        lowered = text.casefold()
        return [match for match in self.text_matches if (match.text.casefold() == lowered if exact else lowered in match.text.casefold())]

    def find_uia(
        self,
        window_id: str,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
        max_results: int = 20,
    ) -> list[ElementInfo]:
        matches = self.uia_matches
        if name is not None:
            lowered = name.casefold()
            matches = [match for match in matches if (match.text.casefold() == lowered if exact else lowered in match.text.casefold())]
        if control_type is not None:
            lowered = control_type.casefold()
            matches = [match for match in matches if ((match.control_type or "").casefold() == lowered if exact else lowered in (match.control_type or "").casefold())]
        if automation_id is not None:
            lowered = automation_id.casefold()
            matches = [match for match in matches if ((match.automation_id or "").casefold() == lowered if exact else lowered in (match.automation_id or "").casefold())]
        return matches[:max_results]

    def find_ocr_text(
        self,
        window_id: str,
        text: str,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> list[ElementInfo]:
        lowered = text.casefold()
        return [
            match
            for match in self.ocr_matches
            if (match.text.casefold() == lowered if exact else lowered in match.text.casefold())
            and (match.confidence or 0.0) >= confidence_threshold
        ]

    def find_image(
        self,
        window_id: str,
        image_path: str,
        threshold: float = 0.9,
        max_results: int = 5,
    ) -> list[ElementInfo]:
        return [match for match in self.image_matches if (match.confidence or 0.0) >= threshold][:max_results]

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        self.screenshot_calls.append((window_id, output_path))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake-image")
        return output_path


class MCPServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temp_dir.name)
        self.engine = AutomationEngine(state_root=self.state_root, driver=FakeDriver())
        self.server = MCPServer(engine=self.engine)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_tools_list_returns_registry(self) -> None:
        response = self.server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])
        self.assertTrue(any(tool["name"] == "start_session" for tool in response["result"]["tools"]))

    def test_tools_call_start_session_and_click(self) -> None:
        session_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "start_session", "arguments": {"profile": "lab_default", "operator": "tester"}},
            }
        )
        session_id = session_response["result"]["session"]["session_id"]

        attach_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "attach_window",
                    "arguments": {"session_id": session_id, "window_id": "win-1"},
                },
            }
        )
        self.assertEqual(attach_response["result"]["window"]["window_id"], "win-1")

        click_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "click",
                    "arguments": {"session_id": session_id, "x": 5, "y": 6},
                },
            }
        )

        self.assertEqual(click_response["result"]["code"], "OK")
        self.assertEqual(self.engine.driver.click_calls, [(105, 206)])

    def test_tools_call_keyboard_actions(self) -> None:
        session_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "start_session", "arguments": {"profile": "lab_default", "operator": "tester"}},
            }
        )
        session_id = session_response["result"]["session"]["session_id"]
        self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "attach_window",
                    "arguments": {"session_id": session_id, "window_id": "win-1"},
                },
            }
        )

        press_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "press_key",
                    "arguments": {"session_id": session_id, "key": "enter"},
                },
            }
        )
        hotkey_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "hotkey",
                    "arguments": {"session_id": session_id, "keys": ["ctrl", "a"]},
                },
            }
        )
        clear_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "clear_text",
                    "arguments": {"session_id": session_id},
                },
            }
        )

        self.assertEqual(press_response["result"]["code"], "OK")
        self.assertEqual(hotkey_response["result"]["code"], "OK")
        self.assertEqual(clear_response["result"]["code"], "OK")
        self.assertEqual(self.engine.driver.key_calls, ["enter"])
        self.assertEqual(self.engine.driver.hotkey_calls, [["ctrl", "a"]])
        self.assertEqual(self.engine.driver.clear_text_calls, 1)

    def test_tools_call_find_text_and_click_text(self) -> None:
        session_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "start_session", "arguments": {"profile": "lab_default"}},
            }
        )
        session_id = session_response["result"]["session"]["session_id"]
        self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "attach_window", "arguments": {"session_id": session_id, "window_id": "win-1"}},
            }
        )

        find_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "find_text", "arguments": {"session_id": session_id, "text": "submit"}},
            }
        )
        click_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "click_text", "arguments": {"session_id": session_id, "text": "submit"}},
            }
        )

        self.assertEqual(len(find_response["result"]["matches"]), 1)
        self.assertEqual(click_response["result"]["code"], "OK")
        self.assertEqual(self.engine.driver.click_calls[-1], (200, 280))

    def test_tools_call_find_uia_ocr_and_image(self) -> None:
        session_response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "start_session", "arguments": {"profile": "lab_default"}},
            }
        )
        session_id = session_response["result"]["session"]["session_id"]
        self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "attach_window", "arguments": {"session_id": session_id, "window_id": "win-1"}},
            }
        )

        find_uia = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "find_uia", "arguments": {"session_id": session_id, "automation_id": "submitButton", "exact": True}},
            }
        )
        click_uia = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "click_uia", "arguments": {"session_id": session_id, "automation_id": "submitButton", "exact": True}},
            }
        )
        find_ocr = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "find_ocr_text", "arguments": {"session_id": session_id, "text": "confirm", "confidence_threshold": 0.8}},
            }
        )
        click_ocr = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "click_ocr", "arguments": {"session_id": session_id, "text": "confirm", "confidence_threshold": 0.8}},
            }
        )
        find_image = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "find_image", "arguments": {"session_id": session_id, "image_path": "button.png", "threshold": 0.95}},
            }
        )
        click_image = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "click_image", "arguments": {"session_id": session_id, "image_path": "button.png", "threshold": 0.95}},
            }
        )

        self.assertEqual(len(find_uia["result"]["matches"]), 1)
        self.assertEqual(click_uia["result"]["code"], "OK")
        self.assertEqual(len(find_ocr["result"]["matches"]), 1)
        self.assertEqual(click_ocr["result"]["code"], "OK")
        self.assertEqual(len(find_image["result"]["matches"]), 1)
        self.assertEqual(click_image["result"]["code"], "OK")
        self.assertEqual(self.engine.driver.click_calls[-3:], [(350, 336), (455, 374), (540, 410)])

    def test_stdio_serve_writes_jsonrpc_response_lines(self) -> None:
        source = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n')
        sink = io.StringIO()

        exit_code = self.server.serve(input_stream=source, output_stream=sink)

        self.assertEqual(exit_code, 0)
        response = json.loads(sink.getvalue().strip())
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])
