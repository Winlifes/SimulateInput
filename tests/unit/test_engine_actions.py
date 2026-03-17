import tempfile
import unittest
from pathlib import Path

from simulateinput.core.engine import AutomationEngine
from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo


class FakeDriver:
    platform = PlatformKind.WINDOWS

    def __init__(self) -> None:
        self.focus_calls: list[str] = []
        self.click_calls: list[tuple[int, int]] = []
        self.drag_calls: list[tuple[int, int, int, int, int]] = []
        self.type_calls: list[str] = []
        self.key_calls: list[str] = []
        self.hotkey_calls: list[list[str]] = []
        self.clear_text_calls = 0
        self.screenshot_calls: list[tuple[str, str]] = []
        self.window = WindowInfo(
            window_id="win-1",
            title="Demo Window",
            platform=self.platform,
            bounds=Bounds(x=100, y=200, width=800, height=600),
        )
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
                "drag",
                "type_text",
                "press_key",
                "hotkey",
                "clear_text",
                "screenshot",
            ]

        return Probe()

    def list_windows(self) -> list[WindowInfo]:
        return [self.window]

    def focus_window(self, window_id: str) -> bool:
        self.focus_calls.append(window_id)
        return True

    def click(self, x: int, y: int) -> None:
        self.click_calls.append((x, y))

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self.drag_calls.append((x1, y1, x2, y2, duration_ms))

    def type_text(self, text: str) -> None:
        self.type_calls.append(text)

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


class EngineActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temp_dir.name)
        self.driver = FakeDriver()
        self.engine = AutomationEngine(state_root=self.state_root, driver=self.driver)
        session = self.engine.sessions.start(profile_name="lab_default", operator="tester")
        self.session_id = session.session_id
        self.engine.attach_window(self.session_id, window_id="win-1")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_execute_click_converts_relative_to_absolute(self) -> None:
        result = self.engine.execute_click(self.session_id, x=10, y=20)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.click_calls, [(110, 220)])

    def test_execute_drag_converts_relative_points(self) -> None:
        result = self.engine.execute_drag(self.session_id, x1=10, y1=20, x2=30, y2=40, duration_ms=500)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.drag_calls, [(110, 220, 130, 240, 500)])

    def test_execute_type_text_uses_active_window(self) -> None:
        result = self.engine.execute_type_text(self.session_id, text="hello")

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.type_calls, ["hello"])

    def test_execute_press_key_uses_active_window(self) -> None:
        result = self.engine.execute_press_key(self.session_id, key="enter")

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.key_calls, ["enter"])

    def test_execute_hotkey_uses_active_window(self) -> None:
        result = self.engine.execute_hotkey(self.session_id, keys=["ctrl", "a"])

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.hotkey_calls, [["ctrl", "a"]])

    def test_execute_clear_text_uses_active_window(self) -> None:
        result = self.engine.execute_clear_text(self.session_id)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.clear_text_calls, 1)

    def test_execute_screenshot_writes_artifact(self) -> None:
        output_path = self.state_root / "captures" / "demo.png"

        result = self.engine.execute_screenshot(self.session_id, output=str(output_path))

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.screenshot_calls, [("win-1", str(output_path))])
        self.assertEqual(result.artifacts[0].path, str(output_path))
        self.assertTrue(output_path.exists())

    def test_find_text_returns_matches(self) -> None:
        matches = self.engine.find_text(self.session_id, text="submit")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].text, "Submit")

    def test_execute_click_text_clicks_match_center(self) -> None:
        result = self.engine.execute_click_text(self.session_id, text="submit")

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.click_calls[-1], (200, 280))

    def test_find_uia_returns_matches(self) -> None:
        matches = self.engine.find_uia(self.session_id, name="submit")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].automation_id, "submitButton")

    def test_execute_click_uia_clicks_match_center(self) -> None:
        result = self.engine.execute_click_uia(self.session_id, automation_id="submitButton", exact=True)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.click_calls[-1], (350, 336))

    def test_execute_click_uia_rejects_non_visible_macos_target(self) -> None:
        self.driver.platform = PlatformKind.MACOS
        self.driver.window.platform = PlatformKind.MACOS
        self.driver.uia_matches = [
            ElementInfo(
                element_id="uia-hidden",
                window_id="win-1",
                platform=PlatformKind.MACOS,
                text="Submit",
                bounds=Bounds(x=300, y=320, width=100, height=32),
                class_name="AXButton",
                control_type="AXButton",
                automation_id="submitButton",
                source="ax",
                confidence=0.9,
                metadata={"visible": False, "enabled": True, "actions": ["axpress"]},
            )
        ]

        with self.assertRaisesRegex(ValueError, "not visible"):
            self.engine.execute_click_uia(self.session_id, automation_id="submitButton", exact=True)

    def test_execute_click_uia_rejects_non_actionable_macos_target(self) -> None:
        self.driver.platform = PlatformKind.MACOS
        self.driver.window.platform = PlatformKind.MACOS
        self.driver.uia_matches = [
            ElementInfo(
                element_id="uia-static",
                window_id="win-1",
                platform=PlatformKind.MACOS,
                text="Submit",
                bounds=Bounds(x=300, y=320, width=100, height=32),
                class_name="AXStaticText",
                control_type="AXStaticText",
                automation_id="submitLabel",
                source="ax",
                confidence=0.9,
                metadata={"visible": True, "enabled": True, "actions": ["axshowdefaultui"]},
            )
        ]

        with self.assertRaisesRegex(ValueError, "not actionable"):
            self.engine.execute_click_uia(self.session_id, automation_id="submitLabel", exact=True)

    def test_find_ocr_text_returns_matches(self) -> None:
        matches = self.engine.find_ocr_text(self.session_id, text="confirm", confidence_threshold=0.8)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].source, "ocr")

    def test_execute_click_ocr_clicks_match_center(self) -> None:
        result = self.engine.execute_click_ocr(self.session_id, text="confirm", confidence_threshold=0.8)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.click_calls[-1], (455, 374))

    def test_find_image_returns_matches(self) -> None:
        matches = self.engine.find_image(self.session_id, image_path="button.png", threshold=0.95)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].source, "image")

    def test_execute_click_image_clicks_match_center(self) -> None:
        result = self.engine.execute_click_image(self.session_id, image_path="button.png", threshold=0.95)

        self.assertTrue(result.ok)
        self.assertEqual(self.driver.click_calls[-1], (540, 410))
