import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import simulateinput.drivers.macos as macos_module
from simulateinput.core.models import Bounds, PlatformKind, WindowInfo
from simulateinput.drivers.macos import MacOSDriver


class MacOSDriverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = MacOSDriver()
        self.window = WindowInfo(
            window_id="123",
            title="Demo Window",
            platform=PlatformKind.MACOS,
            bounds=Bounds(x=10, y=20, width=200, height=100),
            process_name="DemoApp",
        )

    def test_capture_rect_to_bounds_handles_retina_scale(self) -> None:
        bounds = self.driver._capture_rect_to_bounds(
            self.window,
            x=100,
            y=50,
            width=40,
            height=20,
            capture_width=400,
            capture_height=200,
        )

        self.assertEqual(bounds.x, 60)
        self.assertEqual(bounds.y, 45)
        self.assertEqual(bounds.width, 20)
        self.assertEqual(bounds.height, 10)

    def test_capture_rect_to_bounds_preserves_non_retina_scale(self) -> None:
        bounds = self.driver._capture_rect_to_bounds(
            self.window,
            x=24,
            y=18,
            width=30,
            height=12,
            capture_width=200,
            capture_height=100,
        )

        self.assertEqual(bounds.x, 34)
        self.assertEqual(bounds.y, 38)
        self.assertEqual(bounds.width, 30)
        self.assertEqual(bounds.height, 12)

    def test_screenshot_window_uses_shadowless_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "capture.png"
            with patch("simulateinput.drivers.macos.subprocess.run") as run:
                saved_path = self.driver.screenshot_window("123", str(output_path))

        self.assertEqual(saved_path, str(output_path))
        run.assert_called_once_with(
            ["screencapture", "-x", "-o", "-l", "123", str(output_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_focus_window_prefers_specific_window_raise(self) -> None:
        with (
            patch.object(self.driver, "_get_window", return_value=self.window),
            patch.object(self.driver, "_focus_specific_window", return_value=True) as focus_specific,
            patch.object(self.driver, "_activate_application", return_value=True) as activate_application,
        ):
            focused = self.driver.focus_window("123")

        self.assertTrue(focused)
        focus_specific.assert_called_once_with(self.window)
        activate_application.assert_not_called()

    def test_focus_window_falls_back_to_application_activation(self) -> None:
        with (
            patch.object(self.driver, "_get_window", return_value=self.window),
            patch.object(self.driver, "_focus_specific_window", return_value=False) as focus_specific,
            patch.object(self.driver, "_activate_application", return_value=True) as activate_application,
        ):
            focused = self.driver.focus_window("123")

        self.assertTrue(focused)
        focus_specific.assert_called_once_with(self.window)
        activate_application.assert_called_once_with("DemoApp")

    def test_focus_specific_window_passes_window_geometry_to_osascript(self) -> None:
        completed = subprocess.CompletedProcess(args=["osascript"], returncode=0, stdout="true\n", stderr="")
        with patch("simulateinput.drivers.macos.subprocess.run", return_value=completed) as run:
            focused = self.driver._focus_specific_window(self.window)

        self.assertTrue(focused)
        _, kwargs = run.call_args
        self.assertEqual(run.call_args.args[0][:3], ["osascript", "-l", "AppleScript"])
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_PROC_NAME"], "DemoApp")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_TITLE"], "Demo Window")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_X"], "10")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_Y"], "20")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_WIDTH"], "200")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_HEIGHT"], "100")

    def test_find_uia_passes_window_geometry_to_osascript(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout='[{"id":"node-1","text":"Submit","control_type":"AXButton","automation_id":"submitButton","x":30,"y":40,"width":50,"height":20}]\n',
            stderr="",
        )
        with (
            patch.object(self.driver, "_get_window", return_value=self.window),
            patch("simulateinput.drivers.macos.subprocess.run", return_value=completed) as run,
        ):
            matches = self.driver.find_uia("123", name="Submit", exact=True)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].text, "Submit")
        _, kwargs = run.call_args
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_PROC_NAME"], "DemoApp")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_TITLE"], "Demo Window")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_X"], "10")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_Y"], "20")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_WIDTH"], "200")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_WINDOW_HEIGHT"], "100")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_QUERY_NAME"], "Submit")
        self.assertEqual(kwargs["env"]["SIMULATEINPUT_QUERY_EXACT"], "1")

    def test_find_uia_prefers_visible_pressable_controls_and_dedupes(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout=(
                '[{"id":"node-1","text":"Submit","control_type":"AXButton","class_name":"AXButton","automation_id":"submitButton","x":30,"y":40,"width":50,"height":20,"visible":false,"enabled":false,"actions":[]},'
                '{"id":"node-2","text":"Submit","control_type":"AXButton","class_name":"AXButton","automation_id":"submitButton","x":30,"y":40,"width":50,"height":20,"visible":true,"enabled":true,"actions":["AXPress"]},'
                '{"id":"node-3","text":"Submit","control_type":"AXTextField","class_name":"AXTextField","automation_id":"submitField","x":35,"y":75,"width":120,"height":22,"visible":true,"enabled":true,"actions":["AXConfirm"]}]\n'
            ),
            stderr="",
        )
        with (
            patch.object(self.driver, "_get_window", return_value=self.window),
            patch("simulateinput.drivers.macos.subprocess.run", return_value=completed),
        ):
            matches = self.driver.find_uia("123", name="Submit")

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].element_id, "node-2")
        self.assertEqual(matches[0].control_type, "AXButton")
        self.assertEqual(matches[0].automation_id, "submitButton")
        self.assertEqual(matches[0].class_name, "AXButton")
        self.assertEqual(matches[1].element_id, "node-3")

    def test_probe_reports_missing_permissions_and_limits_capabilities(self) -> None:
        fake_quartz = SimpleNamespace(
            AXIsProcessTrusted=lambda: False,
            CGPreflightScreenCaptureAccess=lambda: False,
        )
        with (
            patch.object(macos_module.os, "name", "posix"),
            patch.object(macos_module.os, "uname", return_value=SimpleNamespace(sysname="Darwin")),
            patch.object(self.driver, "_quartz", return_value=fake_quartz),
            patch.object(self.driver, "_probe_automation_permission", return_value=False),
            patch.object(self.driver, "_has_ocr_dependencies", return_value=True),
            patch.object(self.driver, "_has_image_match_dependencies", return_value=True),
        ):
            probe = self.driver.probe()

        self.assertTrue(probe.available)
        self.assertEqual(probe.capabilities, ["probe", "list_windows", "attach_window", "find_text"])
        self.assertIn("missing permissions: Accessibility, Automation, Screen Recording", probe.message)
        self.assertIn("input injection may fail", probe.message)
        self.assertIn("window raise, UIA lookup, and keyboard actions need Automation access", probe.message)
        self.assertIn("screenshots, OCR, and image matching need Screen Recording access", probe.message)
        self.assertEqual(
            probe.details["permissions"],
            {
                "accessibility": {"granted": False, "required_for": ["click", "drag"]},
                "automation": {
                    "granted": False,
                    "required_for": ["focus_window", "find_uia", "type_text", "press_key", "hotkey", "clear_text"],
                },
                "screen_recording": {
                    "granted": False,
                    "required_for": ["screenshot", "find_ocr_text", "find_image"],
                },
            },
        )
        self.assertEqual(
            probe.details["window_matching"],
            {"focus_window": "title-plus-geometry", "find_uia": "title-plus-geometry"},
        )
        self.assertEqual(
            probe.details["remediation"],
            [
                {
                    "kind": "permission",
                    "permission": "Accessibility",
                    "system_settings_path": ["Privacy & Security", "Accessibility"],
                    "shell_hint": "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'",
                    "copyable_steps": [
                        "Open System Settings.",
                        "Go to Privacy & Security > Accessibility.",
                        "Enable access for the app or terminal running SimulateInput.",
                    ],
                    "reason": "Needed for reliable mouse input and some foreground window interactions.",
                },
                {
                    "kind": "permission",
                    "permission": "Automation",
                    "system_settings_path": ["Privacy & Security", "Automation"],
                    "shell_hint": "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation'",
                    "copyable_steps": [
                        "Open System Settings.",
                        "Go to Privacy & Security > Automation.",
                        "Allow the app or terminal running SimulateInput to control System Events.",
                    ],
                    "reason": "Needed to control System Events for window raise, UIA lookup, and keyboard actions.",
                },
                {
                    "kind": "permission",
                    "permission": "Screen Recording",
                    "system_settings_path": ["Privacy & Security", "Screen Recording"],
                    "shell_hint": "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'",
                    "copyable_steps": [
                        "Open System Settings.",
                        "Go to Privacy & Security > Screen Recording.",
                        "Enable access for the app or terminal running SimulateInput.",
                        "Quit and reopen the app if macOS asks for a restart.",
                    ],
                    "reason": "Needed for screenshots, OCR, and image matching.",
                },
            ],
        )

    def test_probe_includes_full_capabilities_when_permissions_are_granted(self) -> None:
        fake_quartz = SimpleNamespace(
            AXIsProcessTrusted=lambda: True,
            CGPreflightScreenCaptureAccess=lambda: True,
        )
        with (
            patch.object(macos_module.os, "name", "posix"),
            patch.object(macos_module.os, "uname", return_value=SimpleNamespace(sysname="Darwin")),
            patch.object(self.driver, "_quartz", return_value=fake_quartz),
            patch.object(self.driver, "_probe_automation_permission", return_value=True),
            patch.object(self.driver, "_has_ocr_dependencies", return_value=True),
            patch.object(self.driver, "_has_image_match_dependencies", return_value=True),
        ):
            probe = self.driver.probe()

        self.assertTrue(probe.available)
        self.assertIn("click", probe.capabilities)
        self.assertIn("drag", probe.capabilities)
        self.assertIn("type_text", probe.capabilities)
        self.assertIn("press_key", probe.capabilities)
        self.assertIn("hotkey", probe.capabilities)
        self.assertIn("clear_text", probe.capabilities)
        self.assertIn("find_uia", probe.capabilities)
        self.assertIn("screenshot", probe.capabilities)
        self.assertIn("find_ocr_text", probe.capabilities)
        self.assertIn("find_image", probe.capabilities)
        self.assertNotIn("missing permissions", probe.message)
        self.assertTrue(probe.details["permissions"]["accessibility"]["granted"])
        self.assertTrue(probe.details["permissions"]["automation"]["granted"])
        self.assertTrue(probe.details["permissions"]["screen_recording"]["granted"])
        self.assertEqual(probe.details["remediation"], [])
