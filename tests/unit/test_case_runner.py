import tempfile
import unittest
from pathlib import Path

from simulateinput.core.engine import AutomationEngine
from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo
from simulateinput.runner.case_runner import load_case, run_case


class FakeDriver:
    platform = PlatformKind.WINDOWS

    def __init__(self) -> None:
        self.click_calls: list[tuple[int, int]] = []
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
            capabilities = ["list_windows", "attach_window", "find_text", "find_image", "click", "screenshot"]

        return Probe()

    def list_windows(self) -> list[WindowInfo]:
        return [self.window]

    def focus_window(self, window_id: str) -> bool:
        return True

    def click(self, x: int, y: int) -> None:
        self.click_calls.append((x, y))

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list[ElementInfo]:
        lowered = text.casefold()
        return [match for match in self.text_matches if lowered in match.text.casefold()]

    def find_image(self, window_id: str, image_path: str, threshold: float = 0.9, max_results: int = 5) -> list[ElementInfo]:
        return [match for match in self.image_matches if (match.confidence or 0.0) >= threshold][:max_results]

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake-image")
        return output_path


class CaseRunnerTest(unittest.TestCase):
    def test_load_case_reads_name_profile_and_steps(self) -> None:
        try:
            import yaml  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("PyYAML is not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            case_path = Path(temp_dir) / "sample.yaml"
            case_path.write_text(
                "\n".join(
                    [
                        "name: sample",
                        "profile: privileged_lab",
                        "steps:",
                        "  - action: attach_window",
                        "    title: Demo",
                    ]
                ),
                encoding="utf-8",
            )

            case_def = load_case(case_path)

            self.assertEqual(case_def.name, "sample")
            self.assertEqual(case_def.profile, "privileged_lab")
            self.assertEqual(len(case_def.steps), 1)

    def test_run_case_executes_locator_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir) / "state"
            case_path = Path(temp_dir) / "sample.yaml"
            shot_path = Path(temp_dir) / "artifacts" / "shot.png"
            case_path.write_text(
                "\n".join(
                    [
                        "name: locator-case",
                        "profile: lab_default",
                        "steps:",
                        "  - action: attach_window",
                        "    window_id: win-1",
                        "  - action: locate_text",
                        "    text: Submit",
                        "  - action: click_text",
                        "    text: Submit",
                        "  - action: locate_image",
                        "    image_path: button.png",
                        "    threshold: 0.95",
                        "  - action: click_image",
                        "    image_path: button.png",
                        "    threshold: 0.95",
                        f"  - action: screenshot\n    output: {shot_path.as_posix()}",
                    ]
                ),
                encoding="utf-8",
            )

            engine = AutomationEngine(state_root=state_root, driver=FakeDriver())
            report = run_case(case_path, engine=engine, operator="tester")

            self.assertEqual(report["name"], "locator-case")
            self.assertEqual(len(report["steps"]), 6)
            self.assertEqual(engine.driver.click_calls, [(200, 280), (540, 410)])
            self.assertTrue(shot_path.exists())
