import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from simulateinput.cli.main import main


class CliMainTest(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, dict]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(args)
        payload = json.loads(buffer.getvalue())
        return exit_code, payload

    def test_doctor_reports_driver_and_tools(self) -> None:
        exit_code, payload = self.run_cli(["doctor"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("driver", payload)
        self.assertIn("mcp_tools", payload)

    def test_mcp_tools_lists_tool_metadata(self) -> None:
        exit_code, payload = self.run_cli(["mcp", "tools"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(any(tool["name"] == "start_session" for tool in payload["tools"]))
        self.assertTrue(any(tool["name"] == "find_uia" for tool in payload["tools"]))
        self.assertTrue(any(tool["name"] == "click_image" for tool in payload["tools"]))

    def test_window_list_returns_windows_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir)
            exit_code, start_payload = self.run_cli(
                [
                    "session",
                    "start",
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)
            session_id = start_payload["session"]["session_id"]

            exit_code, payload = self.run_cli(
                [
                    "window",
                    "list",
                    "--session-id",
                    session_id,
                    "--state-root",
                    str(state_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("windows", payload)
            self.assertIsInstance(payload["windows"], list)

    def test_action_click_preview_uses_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir)
            exit_code, start_payload = self.run_cli(
                [
                    "session",
                    "start",
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)
            session_id = start_payload["session"]["session_id"]

            exit_code, payload = self.run_cli(
                [
                    "action",
                    "click",
                    "--session-id",
                    session_id,
                    "--x",
                    "10",
                    "--y",
                    "20",
                    "--dry-run",
                    "--state-root",
                    str(state_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["code"], "DRY_RUN")
            self.assertEqual(payload["data"]["x"], 10)
            self.assertEqual(payload["data"]["y"], 20)

    def test_action_hotkey_preview_returns_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir)
            exit_code, start_payload = self.run_cli(
                [
                    "session",
                    "start",
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)
            session_id = start_payload["session"]["session_id"]

            exit_code, payload = self.run_cli(
                [
                    "action",
                    "hotkey",
                    "--session-id",
                    session_id,
                    "--keys",
                    "ctrl",
                    "a",
                    "--dry-run",
                    "--state-root",
                    str(state_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["code"], "DRY_RUN")
            self.assertEqual(payload["data"]["keys"], ["ctrl", "a"])

    def test_locate_text_returns_matches_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir)
            exit_code, start_payload = self.run_cli(
                [
                    "session",
                    "start",
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)
            session_id = start_payload["session"]["session_id"]

            exit_code, windows_payload = self.run_cli(
                [
                    "window",
                    "list",
                    "--session-id",
                    session_id,
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue(windows_payload["windows"])
            target_window_id = windows_payload["windows"][0]["window_id"]

            exit_code, _ = self.run_cli(
                [
                    "window",
                    "attach",
                    "--session-id",
                    session_id,
                    "--window-id",
                    target_window_id,
                    "--state-root",
                    str(state_root),
                ]
            )
            self.assertEqual(exit_code, 0)

            exit_code, payload = self.run_cli(
                [
                    "locate",
                    "text",
                    "--session-id",
                    session_id,
                    "--text",
                    windows_payload["windows"][0]["title"],
                    "--exact",
                    "--state-root",
                    str(state_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("matches", payload)
            self.assertIsInstance(payload["matches"], list)
