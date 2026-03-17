from __future__ import annotations

from pathlib import Path

from simulateinput.core.errors import DriverNotAvailableError
from simulateinput.core.models import ActionResult, Artifact, ArtifactKind, ElementInfo, PlatformKind, WindowInfo
from simulateinput.core.session import SessionStore
from simulateinput.drivers.registry import create_driver


class AutomationEngine:
    """Thin orchestration entry point for the initial project skeleton."""

    def __init__(self, state_root: Path | None = None, driver=None) -> None:
        self.state_root = state_root
        self.sessions = SessionStore(root=(state_root / "sessions") if state_root else None)
        self.driver = driver or create_driver()

    def probe_driver(self) -> dict:
        probe = self.driver.probe()
        return {
            "available": probe.available,
            "platform": probe.platform.value,
            "message": probe.message,
            "capabilities": probe.capabilities,
            "details": getattr(probe, "details", {}),
        }

    def list_windows(self, session_id: str) -> list[WindowInfo]:
        _ = self.sessions.get(session_id)
        probe = self.driver.probe()
        if not probe.available or not hasattr(self.driver, "list_windows"):
            raise DriverNotAvailableError(probe.message)
        return self.driver.list_windows()

    def attach_window(
        self,
        session_id: str,
        title: str | None = None,
        window_id: str | None = None,
    ) -> WindowInfo:
        session = self.sessions.get(session_id)
        windows = self.list_windows(session_id)

        match: WindowInfo | None = None
        if window_id is not None:
            for candidate in windows:
                if candidate.window_id == window_id:
                    match = candidate
                    break
        elif title is not None:
            lowered = title.casefold()
            for candidate in windows:
                if lowered in candidate.title.casefold():
                    match = candidate
                    break

        if match is None:
            raise ValueError("no matching window found")

        if hasattr(self.driver, "focus_window"):
            self.driver.focus_window(match.window_id)

        session.metadata["active_window"] = match.to_dict()
        self.sessions.save(session)
        return match

    def _resolve_window(self, session_id: str, window_id: str | None = None) -> WindowInfo:
        session = self.sessions.get(session_id)
        resolved_window_id = window_id or session.metadata.get("active_window", {}).get("window_id")
        if resolved_window_id is None:
            raise ValueError("action requires --window-id or an attached active window")

        for candidate in self.list_windows(session_id):
            if candidate.window_id == resolved_window_id:
                session.metadata["active_window"] = candidate.to_dict()
                self.sessions.save(session)
                return candidate

        active_window = session.metadata.get("active_window")
        if active_window and active_window.get("window_id") == resolved_window_id:
            return WindowInfo.from_dict(active_window)

        raise ValueError(f"window not found: {resolved_window_id}")

    def _focus_window(self, window: WindowInfo) -> None:
        if hasattr(self.driver, "focus_window"):
            self.driver.focus_window(window.window_id)

    def find_text(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
    ) -> list[ElementInfo]:
        window = self._resolve_window(session_id, window_id=window_id)
        if not hasattr(self.driver, "find_text"):
            raise DriverNotAvailableError("current driver does not support text lookup")
        return self.driver.find_text(window.window_id, text, exact=exact)

    def find_uia(
        self,
        session_id: str,
        window_id: str | None = None,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
        max_results: int = 20,
    ) -> list[ElementInfo]:
        window = self._resolve_window(session_id, window_id=window_id)
        if not hasattr(self.driver, "find_uia"):
            raise DriverNotAvailableError("current driver does not support UIA lookup")
        return self.driver.find_uia(
            window.window_id,
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            exact=exact,
            max_results=max_results,
        )

    def find_ocr_text(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> list[ElementInfo]:
        window = self._resolve_window(session_id, window_id=window_id)
        if not hasattr(self.driver, "find_ocr_text"):
            raise DriverNotAvailableError("current driver does not support OCR lookup")
        return self.driver.find_ocr_text(
            window.window_id,
            text,
            exact=exact,
            confidence_threshold=confidence_threshold,
        )

    def find_image(
        self,
        session_id: str,
        image_path: str,
        window_id: str | None = None,
        threshold: float = 0.9,
        max_results: int = 5,
    ) -> list[ElementInfo]:
        window = self._resolve_window(session_id, window_id=window_id)
        if not hasattr(self.driver, "find_image"):
            raise DriverNotAvailableError("current driver does not support image lookup")
        return self.driver.find_image(
            window.window_id,
            image_path,
            threshold=threshold,
            max_results=max_results,
        )

    def _build_center_payload(self, target: ElementInfo) -> dict:
        center_x = target.bounds.x + (target.bounds.width // 2)
        center_y = target.bounds.y + (target.bounds.height // 2)
        return {
            "window_id": target.window_id,
            "element": target.to_dict(),
            "absolute": {"x": center_x, "y": center_y},
        }

    def preview_click_text(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
    ) -> ActionResult:
        matches = self.find_text(session_id, text, window_id=window_id, exact=exact)
        if not matches:
            raise ValueError(f"text target not found: {text}")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="click_text preview generated",
            data=self._build_center_payload(matches[0]),
        )

    def execute_click_text(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
    ) -> ActionResult:
        matches = self.find_text(session_id, text, window_id=window_id, exact=exact)
        if not matches:
            raise ValueError(f"text target not found: {text}")
        target = matches[0]
        window = self._resolve_window(session_id, window_id=target.window_id)
        self._focus_window(window)
        payload = self._build_center_payload(target)
        center_x = payload["absolute"]["x"]
        center_y = payload["absolute"]["y"]
        self.driver.click(center_x, center_y)
        return ActionResult(
            ok=True,
            code="OK",
            message="click_text executed",
            data=payload,
        )

    def preview_click_uia(
        self,
        session_id: str,
        window_id: str | None = None,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
    ) -> ActionResult:
        matches = self.find_uia(
            session_id,
            window_id=window_id,
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            exact=exact,
        )
        if not matches:
            raise ValueError("uia target not found")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="click_uia preview generated",
            data=self._build_center_payload(matches[0]),
        )

    def execute_click_uia(
        self,
        session_id: str,
        window_id: str | None = None,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
    ) -> ActionResult:
        matches = self.find_uia(
            session_id,
            window_id=window_id,
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            exact=exact,
        )
        if not matches:
            raise ValueError("uia target not found")
        target = matches[0]
        self._validate_clickable_uia_target(target)
        window = self._resolve_window(session_id, window_id=target.window_id)
        self._focus_window(window)
        payload = self._build_center_payload(target)
        self.driver.click(payload["absolute"]["x"], payload["absolute"]["y"])
        return ActionResult(ok=True, code="OK", message="click_uia executed", data=payload)

    def _validate_clickable_uia_target(self, target: ElementInfo) -> None:
        if target.platform != PlatformKind.MACOS:
            return
        metadata = target.metadata or {}
        if not metadata:
            return

        if metadata.get("visible") is False:
            raise ValueError("macOS UIA target is not visible")
        if metadata.get("enabled") is False:
            raise ValueError("macOS UIA target is disabled")
        if int(target.bounds.width) <= 0 or int(target.bounds.height) <= 0:
            raise ValueError("macOS UIA target has no clickable size")

        actions = {
            str(action).strip().casefold()
            for action in metadata.get("actions", [])
            if str(action).strip()
        }
        actionable_actions = {
            "axpress",
            "axconfirm",
            "axshowmenu",
            "axpick",
            "axopen",
            "axincrement",
            "axdecrement",
        }
        interactive_roles = {
            "axbutton",
            "axcheckbox",
            "axradiobutton",
            "axpopbutton",
            "axmenuitem",
            "axtextfield",
            "axsecuretextfield",
            "axlink",
            "axdisclosuretriangle",
        }
        control_type = (target.control_type or "").casefold()
        if actions and not (actions & actionable_actions) and control_type not in interactive_roles:
            raise ValueError("macOS UIA target is not actionable for click_uia")

    def preview_click_ocr(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> ActionResult:
        matches = self.find_ocr_text(
            session_id,
            text,
            window_id=window_id,
            exact=exact,
            confidence_threshold=confidence_threshold,
        )
        if not matches:
            raise ValueError(f"ocr target not found: {text}")
        return ActionResult(ok=True, code="DRY_RUN", message="click_ocr preview generated", data=self._build_center_payload(matches[0]))

    def execute_click_ocr(
        self,
        session_id: str,
        text: str,
        window_id: str | None = None,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> ActionResult:
        matches = self.find_ocr_text(
            session_id,
            text,
            window_id=window_id,
            exact=exact,
            confidence_threshold=confidence_threshold,
        )
        if not matches:
            raise ValueError(f"ocr target not found: {text}")
        target = matches[0]
        window = self._resolve_window(session_id, window_id=target.window_id)
        self._focus_window(window)
        payload = self._build_center_payload(target)
        self.driver.click(payload["absolute"]["x"], payload["absolute"]["y"])
        return ActionResult(ok=True, code="OK", message="click_ocr executed", data=payload)

    def preview_click_image(
        self,
        session_id: str,
        image_path: str,
        window_id: str | None = None,
        threshold: float = 0.9,
    ) -> ActionResult:
        matches = self.find_image(session_id, image_path, window_id=window_id, threshold=threshold)
        if not matches:
            raise ValueError(f"image target not found: {image_path}")
        return ActionResult(ok=True, code="DRY_RUN", message="click_image preview generated", data=self._build_center_payload(matches[0]))

    def execute_click_image(
        self,
        session_id: str,
        image_path: str,
        window_id: str | None = None,
        threshold: float = 0.9,
    ) -> ActionResult:
        matches = self.find_image(session_id, image_path, window_id=window_id, threshold=threshold)
        if not matches:
            raise ValueError(f"image target not found: {image_path}")
        target = matches[0]
        window = self._resolve_window(session_id, window_id=target.window_id)
        self._focus_window(window)
        payload = self._build_center_payload(target)
        self.driver.click(payload["absolute"]["x"], payload["absolute"]["y"])
        return ActionResult(ok=True, code="OK", message="click_image executed", data=payload)

    def preview_click(self, session_id: str, x: int, y: int, window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="click preview generated",
            data={"window_id": active_window, "x": x, "y": y},
        )

    def execute_click(self, session_id: str, x: int, y: int, window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        absolute_x = window.bounds.x + x
        absolute_y = window.bounds.y + y
        self.driver.click(absolute_x, absolute_y)
        return ActionResult(
            ok=True,
            code="OK",
            message="click executed",
            data={
                "window_id": window.window_id,
                "relative": {"x": x, "y": y},
                "absolute": {"x": absolute_x, "y": absolute_y},
            },
        )

    def preview_drag(
        self,
        session_id: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int,
        window_id: str | None = None,
    ) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="drag preview generated",
            data={
                "window_id": active_window,
                "from": {"x": x1, "y": y1},
                "to": {"x": x2, "y": y2},
                "duration_ms": duration_ms,
            },
        )

    def execute_drag(
        self,
        session_id: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int,
        window_id: str | None = None,
    ) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        absolute_x1 = window.bounds.x + x1
        absolute_y1 = window.bounds.y + y1
        absolute_x2 = window.bounds.x + x2
        absolute_y2 = window.bounds.y + y2
        self.driver.drag(absolute_x1, absolute_y1, absolute_x2, absolute_y2, duration_ms=duration_ms)
        return ActionResult(
            ok=True,
            code="OK",
            message="drag executed",
            data={
                "window_id": window.window_id,
                "from": {"relative": {"x": x1, "y": y1}, "absolute": {"x": absolute_x1, "y": absolute_y1}},
                "to": {"relative": {"x": x2, "y": y2}, "absolute": {"x": absolute_x2, "y": absolute_y2}},
                "duration_ms": duration_ms,
            },
        )

    def preview_type_text(self, session_id: str, text: str, window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="type_text preview generated",
            data={"window_id": active_window, "text": text, "length": len(text)},
        )

    def execute_type_text(self, session_id: str, text: str, window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        self.driver.type_text(text)
        return ActionResult(
            ok=True,
            code="OK",
            message="type_text executed",
            data={"window_id": window.window_id, "text": text, "length": len(text)},
        )

    def preview_press_key(self, session_id: str, key: str, window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="press_key preview generated",
            data={"window_id": active_window, "key": key},
        )

    def execute_press_key(self, session_id: str, key: str, window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        self.driver.press_key(key)
        return ActionResult(
            ok=True,
            code="OK",
            message="press_key executed",
            data={"window_id": window.window_id, "key": key},
        )

    def preview_hotkey(self, session_id: str, keys: list[str], window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="hotkey preview generated",
            data={"window_id": active_window, "keys": keys},
        )

    def execute_hotkey(self, session_id: str, keys: list[str], window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        self.driver.hotkey(keys)
        return ActionResult(
            ok=True,
            code="OK",
            message="hotkey executed",
            data={"window_id": window.window_id, "keys": keys},
        )

    def preview_clear_text(self, session_id: str, window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="clear_text preview generated",
            data={"window_id": active_window},
        )

    def execute_clear_text(self, session_id: str, window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        self.driver.clear_text()
        return ActionResult(
            ok=True,
            code="OK",
            message="clear_text executed",
            data={"window_id": window.window_id},
        )

    def preview_screenshot(self, session_id: str, output: str, window_id: str | None = None) -> ActionResult:
        session = self.sessions.get(session_id)
        active_window = window_id or session.metadata.get("active_window", {}).get("window_id")
        return ActionResult(
            ok=True,
            code="DRY_RUN",
            message="screenshot preview generated",
            data={"window_id": active_window, "output": output},
        )

    def execute_screenshot(self, session_id: str, output: str, window_id: str | None = None) -> ActionResult:
        window = self._resolve_window(session_id, window_id=window_id)
        self._focus_window(window)
        resolved_output = Path(output)
        saved_path = self.driver.screenshot_window(window.window_id, str(resolved_output))
        return ActionResult(
            ok=True,
            code="OK",
            message="screenshot executed",
            data={"window_id": window.window_id, "output": saved_path},
            artifacts=[Artifact(kind=ArtifactKind.SCREENSHOT, path=saved_path, label="window-screenshot")],
        )
