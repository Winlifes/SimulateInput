from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo
from simulateinput.drivers.base import DriverProbe
from simulateinput.drivers.diagnostics import permission_remediation

KEY_CODE_MAP = {
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "backspace": 51,
    "escape": 53,
    "esc": 53,
    "command": 55,
    "cmd": 55,
    "shift": 56,
    "capslock": 57,
    "option": 58,
    "alt": 58,
    "control": 59,
    "ctrl": 59,
    "rightshift": 60,
    "rightoption": 61,
    "rightcontrol": 62,
    "function": 63,
    "f17": 64,
    "volumeup": 72,
    "volumedown": 73,
    "mute": 74,
    "f18": 79,
    "f19": 80,
    "f20": 90,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f3": 99,
    "f8": 100,
    "f9": 101,
    "f11": 103,
    "f13": 105,
    "f16": 106,
    "f14": 107,
    "f10": 109,
    "f12": 111,
    "f15": 113,
    "help": 114,
    "home": 115,
    "pageup": 116,
    "forwarddelete": 117,
    "end": 119,
    "f2": 120,
    "pagedown": 121,
    "f1": 122,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}


class MacOSDriver:
    platform = PlatformKind.MACOS

    def probe(self) -> DriverProbe:
        if os.name != "posix" or os.uname().sysname != "Darwin":
            return DriverProbe(
                available=False,
                platform=self.platform,
                message="macOS driver is unavailable on this platform",
            )
        try:
            self._quartz()
        except Exception as exc:
            return DriverProbe(
                available=False,
                platform=self.platform,
                message=f"macOS driver requires pyobjc Quartz bindings: {exc}",
            )
        quartz = self._quartz()
        accessibility_granted = self._probe_accessibility_permission(quartz)
        automation_granted = self._probe_automation_permission()
        screen_recording_granted = self._probe_screen_recording_permission(quartz)
        ocr_dependencies = self._has_ocr_dependencies()
        image_dependencies = self._has_image_match_dependencies()

        capabilities = [
            "probe",
            "list_windows",
            "attach_window",
            "find_text",
        ]
        if accessibility_granted is not False:
            capabilities.extend(["click", "drag"])
        if automation_granted is not False:
            capabilities.extend(["type_text", "press_key", "hotkey", "clear_text"])
        if accessibility_granted is not False and automation_granted is not False:
            capabilities.append("find_uia")
        if screen_recording_granted is not False:
            capabilities.append("screenshot")
            if ocr_dependencies:
                capabilities.append("find_ocr_text")
            if image_dependencies:
                capabilities.append("find_image")

        missing_permissions: list[str] = []
        if accessibility_granted is False:
            missing_permissions.append("Accessibility")
        if automation_granted is False:
            missing_permissions.append("Automation")
        if screen_recording_granted is False:
            missing_permissions.append("Screen Recording")

        unknown_permissions: list[str] = []
        if accessibility_granted is None:
            unknown_permissions.append("Accessibility")
        if automation_granted is None:
            unknown_permissions.append("Automation")
        if screen_recording_granted is None:
            unknown_permissions.append("Screen Recording")

        notes: list[str] = []
        if missing_permissions:
            notes.append(f"missing permissions: {', '.join(missing_permissions)}")
        if accessibility_granted is False:
            notes.append("input injection may fail until Accessibility access is granted")
        if automation_granted is False:
            notes.append("window raise, UIA lookup, and keyboard actions need Automation access to System Events")
        if screen_recording_granted is False:
            notes.append("screenshots, OCR, and image matching need Screen Recording access")
        if unknown_permissions:
            notes.append(f"permission preflight unavailable for: {', '.join(unknown_permissions)}")

        message = "macOS driver available with Quartz input, window enumeration, and accessibility lookup"
        if notes:
            message += "; " + "; ".join(notes)
        details = {
            "permissions": {
                "accessibility": {
                    "granted": accessibility_granted,
                    "required_for": ["click", "drag"],
                },
                "automation": {
                    "granted": automation_granted,
                    "required_for": ["focus_window", "find_uia", "type_text", "press_key", "hotkey", "clear_text"],
                },
                "screen_recording": {
                    "granted": screen_recording_granted,
                    "required_for": ["screenshot", "find_ocr_text", "find_image"],
                },
            },
            "dependencies": {
                "pyobjc_quartz": True,
                "ocr": ocr_dependencies,
                "image_match": image_dependencies,
                "tesseract_cmd": self._resolve_tesseract_cmd(),
            },
            "window_matching": {
                "focus_window": "title-plus-geometry",
                "find_uia": "title-plus-geometry",
            },
            "remediation": self._build_remediation_hints(
                accessibility_granted=accessibility_granted,
                automation_granted=automation_granted,
                screen_recording_granted=screen_recording_granted,
            ),
        }
        return DriverProbe(
            available=True,
            platform=self.platform,
            message=message,
            capabilities=list(dict.fromkeys(capabilities)),
            details=details,
        )

    def list_windows(self) -> list[WindowInfo]:
        quartz = self._quartz()
        window_list = quartz.CGWindowListCopyWindowInfo(
            quartz.kCGWindowListOptionOnScreenOnly,
            quartz.kCGNullWindowID,
        )
        windows: list[WindowInfo] = []
        for window in window_list:
            title = str(window.get("kCGWindowName") or "").strip()
            owner = str(window.get("kCGWindowOwnerName") or "").strip()
            if not title:
                continue
            bounds = window.get("kCGWindowBounds") or {}
            windows.append(
                WindowInfo(
                    window_id=str(int(window.get("kCGWindowNumber"))),
                    title=title,
                    platform=self.platform,
                    bounds=Bounds(
                        x=int(bounds.get("X", 0)),
                        y=int(bounds.get("Y", 0)),
                        width=int(bounds.get("Width", 0)),
                        height=int(bounds.get("Height", 0)),
                    ),
                    process_id=int(window.get("kCGWindowOwnerPID")) if window.get("kCGWindowOwnerPID") is not None else None,
                    process_name=owner or None,
                    is_visible=True,
                )
            )
        return windows

    def focus_window(self, window_id: str) -> bool:
        try:
            window = self._get_window(window_id)
        except ValueError:
            return False
        if not window.process_name:
            return False
        if self._focus_specific_window(window):
            return True
        return self._activate_application(window.process_name)

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list[ElementInfo]:
        query = text.strip()
        if not query:
            raise ValueError("text query must not be empty")
        window = self._get_window(window_id)
        matches: list[ElementInfo] = []
        lowered = query.casefold()
        title_match = window.title.casefold() == lowered if exact else lowered in window.title.casefold()
        if title_match:
            matches.append(
                ElementInfo(
                    element_id=f"mac-window-{window.window_id}",
                    window_id=window.window_id,
                    platform=self.platform,
                    text=window.title,
                    bounds=window.bounds,
                    control_type="window",
                    source="window-title",
                    confidence=1.0 if exact else 0.8,
                )
            )
        try:
            matches.extend(self.find_uia(window_id, name=query, exact=exact, max_results=20))
        except Exception:
            pass
        return self._dedupe_elements(matches)

    def find_uia(
        self,
        window_id: str,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
        max_results: int = 20,
    ) -> list[ElementInfo]:
        if name is None and control_type is None and automation_id is None:
            raise ValueError("find_uia requires at least one filter")
        window = self._get_window(window_id)
        if not window.process_name:
            return []
        script = self._build_uia_script()
        env = self._window_context_env(window)
        env["SIMULATEINPUT_QUERY_NAME"] = name or ""
        env["SIMULATEINPUT_QUERY_ROLE"] = control_type or ""
        env["SIMULATEINPUT_QUERY_AID"] = automation_id or ""
        env["SIMULATEINPUT_QUERY_EXACT"] = "1" if exact else "0"
        result = subprocess.run(
            ["osascript", "-l", "AppleScript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        payload = result.stdout.strip()
        if not payload:
            return []
        parsed = json.loads(payload)
        return self._rank_uia_matches(window, parsed, exact=exact, max_results=max_results)

    def find_ocr_text(
        self,
        window_id: str,
        text: str,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> list[ElementInfo]:
        try:
            import pytesseract
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise RuntimeError("pytesseract and pillow are required for OCR lookup") from exc
        tesseract_cmd = self._resolve_tesseract_cmd()
        if tesseract_cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise RuntimeError("Tesseract OCR is not installed or not on PATH") from exc
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            self.screenshot_window(window_id, str(temp_path))
            image = Image.open(temp_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            window = self._get_window(window_id)
            capture_width, capture_height = self._capture_image_size(image)
            lowered = text.casefold()
            matches: list[ElementInfo] = []
            for index, candidate_text in enumerate(data.get("text", [])):
                normalized = str(candidate_text).strip()
                if not normalized:
                    continue
                try:
                    confidence = float(data.get("conf", ["-1"])[index])
                except (TypeError, ValueError):
                    confidence = -1.0
                if confidence < confidence_threshold:
                    continue
                matched = normalized.casefold() == lowered if exact else lowered in normalized.casefold()
                if not matched:
                    continue
                bounds = self._capture_rect_to_bounds(
                    window,
                    x=int(data["left"][index]),
                    y=int(data["top"][index]),
                    width=int(data["width"][index]),
                    height=int(data["height"][index]),
                    capture_width=capture_width,
                    capture_height=capture_height,
                )
                matches.append(
                    ElementInfo(
                        element_id=f"ocr-{window_id}-{index}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=normalized,
                        bounds=bounds,
                        control_type="ocr-text",
                        source="ocr",
                        confidence=max(confidence / 100.0, 0.0),
                    )
                )
            return matches
        finally:
            temp_path.unlink(missing_ok=True)

    def find_image(
        self,
        window_id: str,
        image_path: str,
        threshold: float = 0.9,
        max_results: int = 5,
    ) -> list[ElementInfo]:
        try:
            import cv2
            import numpy as np
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise RuntimeError("opencv-python-headless, numpy, and pillow are required for image lookup") from exc
        template_path = Path(image_path)
        if not template_path.exists():
            raise ValueError(f"image template not found: {image_path}")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            self.screenshot_window(window_id, str(temp_path))
            capture_image = Image.open(temp_path).convert("RGB")
            capture_width, capture_height = self._capture_image_size(capture_image)
            screen = cv2.cvtColor(np.array(capture_image), cv2.COLOR_RGB2BGR)
            template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
            if template is None:
                raise ValueError(f"failed to read image template: {image_path}")
            scales = [0.75, 0.9, 1.0, 1.1, 1.25]
            locations: list[tuple[float, int, int, int, int]] = []
            original_height, original_width = template.shape[:2]
            for scale in scales:
                scaled_width = max(1, int(round(original_width * scale)))
                scaled_height = max(1, int(round(original_height * scale)))
                if scaled_width > screen.shape[1] or scaled_height > screen.shape[0]:
                    continue
                scaled_template = template if scale == 1.0 else cv2.resize(
                    template,
                    (scaled_width, scaled_height),
                    interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
                )
                result = cv2.matchTemplate(screen, scaled_template, cv2.TM_CCOEFF_NORMED)
                ys, xs = (result >= threshold).nonzero()
                for y, x in zip(ys, xs):
                    locations.append((float(result[y, x]), int(x), int(y), int(scaled_width), int(scaled_height)))
            locations.sort(reverse=True, key=lambda item: item[0])
            window = self._get_window(window_id)
            matches: list[ElementInfo] = []
            accepted: list[tuple[int, int, int, int]] = []
            for score, x, y, width, height in locations:
                box = (x, y, width, height)
                if any(self._iou(box, other) >= 0.35 for other in accepted):
                    continue
                accepted.append(box)
                bounds = self._capture_rect_to_bounds(
                    window,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    capture_width=capture_width,
                    capture_height=capture_height,
                )
                matches.append(
                    ElementInfo(
                        element_id=f"img-{window_id}-{len(matches)}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=template_path.name,
                        bounds=bounds,
                        control_type="image-template",
                        source="image",
                        confidence=score,
                    )
                )
                if len(matches) >= max_results:
                    break
            return matches
        finally:
            temp_path.unlink(missing_ok=True)

    def click(self, x: int, y: int) -> None:
        quartz = self._quartz()
        point = (float(x), float(y))
        down = quartz.CGEventCreateMouseEvent(None, quartz.kCGEventLeftMouseDown, point, quartz.kCGMouseButtonLeft)
        up = quartz.CGEventCreateMouseEvent(None, quartz.kCGEventLeftMouseUp, point, quartz.kCGMouseButtonLeft)
        quartz.CGEventPost(quartz.kCGHIDEventTap, down)
        time.sleep(0.02)
        quartz.CGEventPost(quartz.kCGHIDEventTap, up)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, steps: int = 24) -> None:
        quartz = self._quartz()
        start = (float(x1), float(y1))
        quartz.CGEventPost(quartz.kCGHIDEventTap, quartz.CGEventCreateMouseEvent(None, quartz.kCGEventMouseMoved, start, quartz.kCGMouseButtonLeft))
        time.sleep(0.02)
        quartz.CGEventPost(quartz.kCGHIDEventTap, quartz.CGEventCreateMouseEvent(None, quartz.kCGEventLeftMouseDown, start, quartz.kCGMouseButtonLeft))
        sleep_interval = max(duration_ms, 0) / max(steps, 1) / 1000.0
        for index in range(1, max(steps, 1) + 1):
            progress = index / max(steps, 1)
            point = (float(x1 + ((x2 - x1) * progress)), float(y1 + ((y2 - y1) * progress)))
            quartz.CGEventPost(quartz.kCGHIDEventTap, quartz.CGEventCreateMouseEvent(None, quartz.kCGEventLeftMouseDragged, point, quartz.kCGMouseButtonLeft))
            if sleep_interval > 0:
                time.sleep(sleep_interval)
        end = (float(x2), float(y2))
        quartz.CGEventPost(quartz.kCGHIDEventTap, quartz.CGEventCreateMouseEvent(None, quartz.kCGEventLeftMouseUp, end, quartz.kCGMouseButtonLeft))

    def type_text(self, text: str) -> None:
        self._run_osascript(f'tell application "System Events" to keystroke "{self._escape_applescript(text)}"')

    def press_key(self, key: str) -> None:
        self._send_keystroke(key)

    def hotkey(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("hotkey requires at least one key")
        modifiers = [self._modifier_name(key) for key in keys[:-1]]
        self._send_keystroke(keys[-1], modifiers=modifiers)

    def clear_text(self) -> None:
        self.hotkey(["cmd", "a"])
        time.sleep(0.02)
        self.press_key("delete")

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["screencapture", "-x", "-o", "-l", str(window_id), str(output)], check=True, capture_output=True, text=True)
        return str(output)

    def _send_keystroke(self, key: str, modifiers: list[str] | None = None) -> None:
        normalized = key.strip().lower()
        modifiers = modifiers or []
        using_clause = ""
        if modifiers:
            using_clause = " using {" + ", ".join(f"{name} down" for name in modifiers) + "}"
        if len(normalized) == 1 and normalized.isprintable():
            self._run_osascript(f'tell application "System Events" to keystroke "{self._escape_applescript(normalized)}"{using_clause}')
            return
        if normalized not in KEY_CODE_MAP:
            raise ValueError(f"unsupported macOS key: {key}")
        self._run_osascript(f'tell application "System Events" to key code {KEY_CODE_MAP[normalized]}{using_clause}')

    def _modifier_name(self, key: str) -> str:
        normalized = key.strip().lower()
        mapping = {
            "cmd": "command",
            "command": "command",
            "ctrl": "control",
            "control": "control",
            "shift": "shift",
            "alt": "option",
            "option": "option",
        }
        if normalized not in mapping:
            raise ValueError(f"unsupported macOS modifier: {key}")
        return mapping[normalized]

    def _run_osascript(self, script: str) -> str:
        result = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def _escape_applescript(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _quartz(self):  # type: ignore[no-untyped-def]
        try:
            import Quartz
        except ModuleNotFoundError as exc:
            raise RuntimeError("install pyobjc-framework-Quartz on macOS") from exc
        return Quartz

    def _get_window(self, window_id: str) -> WindowInfo:
        for window in self.list_windows():
            if window.window_id == str(window_id):
                return window
        raise ValueError(f"window not found: {window_id}")

    def _resolve_tesseract_cmd(self) -> str | None:
        configured = os.environ.get("TESSERACT_CMD")
        if configured and Path(configured).exists():
            return configured
        discovered = shutil.which("tesseract")
        if discovered:
            return discovered
        for candidate in (Path("/opt/homebrew/bin/tesseract"), Path("/usr/local/bin/tesseract")):
            if candidate.exists():
                return str(candidate)
        return None

    def _has_ocr_dependencies(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ModuleNotFoundError:
            return False
        return self._resolve_tesseract_cmd() is not None

    def _has_image_match_dependencies(self) -> bool:
        try:
            import cv2  # noqa: F401
            from PIL import Image  # noqa: F401
            import numpy  # noqa: F401
        except ModuleNotFoundError:
            return False
        return True

    def _probe_accessibility_permission(self, quartz: object | None = None) -> bool | None:
        runtime = quartz or self._quartz()
        checker = getattr(runtime, "AXIsProcessTrusted", None)
        if checker is None:
            return None
        try:
            return bool(checker())
        except Exception:
            return None

    def _probe_screen_recording_permission(self, quartz: object | None = None) -> bool | None:
        runtime = quartz or self._quartz()
        checker = getattr(runtime, "CGPreflightScreenCaptureAccess", None)
        if checker is None:
            return None
        try:
            return bool(checker())
        except Exception:
            return None

    def _probe_automation_permission(self) -> bool | None:
        try:
            self._run_osascript('tell application "System Events" to get name of first process')
            return True
        except subprocess.CalledProcessError as exc:
            details = " ".join(
                part for part in (exc.stdout, exc.stderr, str(exc)) if part
            ).casefold()
            markers = [
                "not authorized",
                "not permitted",
                "not allowed",
                "automation",
                "assistive access",
                "-1743",
                "-25211",
            ]
            if any(marker in details for marker in markers):
                return False
            return None
        except Exception:
            return None

    def _build_remediation_hints(
        self,
        accessibility_granted: bool | None,
        automation_granted: bool | None,
        screen_recording_granted: bool | None,
    ) -> list[dict[str, object]]:
        hints: list[dict[str, object]] = []
        if accessibility_granted is False:
            hints.append(
                permission_remediation(
                    "Accessibility",
                    "Needed for reliable mouse input and some foreground window interactions.",
                    ["Privacy & Security", "Accessibility"],
                    shell_hint="open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'",
                    copyable_steps=[
                        "Open System Settings.",
                        "Go to Privacy & Security > Accessibility.",
                        "Enable access for the app or terminal running SimulateInput.",
                    ],
                )
            )
        if automation_granted is False:
            hints.append(
                permission_remediation(
                    "Automation",
                    "Needed to control System Events for window raise, UIA lookup, and keyboard actions.",
                    ["Privacy & Security", "Automation"],
                    shell_hint="open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation'",
                    copyable_steps=[
                        "Open System Settings.",
                        "Go to Privacy & Security > Automation.",
                        "Allow the app or terminal running SimulateInput to control System Events.",
                    ],
                )
            )
        if screen_recording_granted is False:
            hints.append(
                permission_remediation(
                    "Screen Recording",
                    "Needed for screenshots, OCR, and image matching.",
                    ["Privacy & Security", "Screen Recording"],
                    shell_hint="open 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'",
                    copyable_steps=[
                        "Open System Settings.",
                        "Go to Privacy & Security > Screen Recording.",
                        "Enable access for the app or terminal running SimulateInput.",
                        "Quit and reopen the app if macOS asks for a restart.",
                    ],
                )
            )
        return hints

    def _rank_uia_matches(
        self,
        window: WindowInfo,
        parsed: list[dict[str, object]],
        exact: bool,
        max_results: int,
    ) -> list[ElementInfo]:
        ranked: list[tuple[tuple[float, int, int, int], ElementInfo]] = []
        for index, item in enumerate(parsed):
            element = ElementInfo(
                element_id=str(item.get("id") or f"mac-ax-{index}"),
                window_id=window.window_id,
                platform=self.platform,
                text=str(item.get("text") or ""),
                bounds=Bounds(
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=int(item.get("width", 0)),
                    height=int(item.get("height", 0)),
                ),
                class_name=item.get("class_name"),
                control_type=item.get("control_type"),
                automation_id=item.get("automation_id"),
                source="ax",
                confidence=self._uia_confidence(item, exact=exact),
                metadata={
                    "visible": self._coerce_bool(item.get("visible")),
                    "enabled": self._coerce_bool(item.get("enabled")),
                    "actions": sorted(self._normalize_action_names(item.get("actions"))),
                },
            )
            ranked.append((self._uia_sort_key(item, element), element))

        ranked.sort(key=lambda item: item[0])
        deduped: list[ElementInfo] = []
        seen: set[tuple[str, str, str, int, int, int, int]] = set()
        for _, element in ranked:
            key = (
                element.text,
                element.control_type or "",
                element.automation_id or "",
                int(element.bounds.x),
                int(element.bounds.y),
                int(element.bounds.width),
                int(element.bounds.height),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(element)
            if len(deduped) >= max_results:
                break
        return deduped

    def _uia_confidence(self, item: dict[str, object], exact: bool) -> float:
        score = self._uia_match_score(item)
        base = 0.72 if exact else 0.58
        cap = 0.99 if exact else 0.95
        return min(cap, base + (score / 220.0))

    def _uia_sort_key(self, item: dict[str, object], element: ElementInfo) -> tuple[float, int, int, int]:
        score = self._uia_match_score(item)
        return (
            -score,
            int(element.bounds.y),
            int(element.bounds.x),
            len(element.text or ""),
        )

    def _uia_match_score(self, item: dict[str, object]) -> float:
        score = 0.0
        if self._coerce_bool(item.get("visible")) is True:
            score += 40.0
        if self._coerce_bool(item.get("enabled")) is True:
            score += 25.0
        action_names = self._normalize_action_names(item.get("actions"))
        if "axpress" in action_names:
            score += 25.0
        elif action_names:
            score += 10.0

        control_type = str(item.get("control_type") or "").casefold()
        preferred_roles = {
            "axbutton": 18.0,
            "axcheckbox": 16.0,
            "axradiobutton": 16.0,
            "axpopbutton": 15.0,
            "axmenuitem": 14.0,
            "axtextfield": 12.0,
            "axsecuretextfield": 12.0,
        }
        score += preferred_roles.get(control_type, 0.0)

        width = max(int(item.get("width", 0) or 0), 0)
        height = max(int(item.get("height", 0) or 0), 0)
        if width > 0 and height > 0:
            score += 5.0
        if width >= 8 and height >= 8:
            score += 4.0
        return score

    def _coerce_bool(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        return None

    def _normalize_action_names(self, actions: object) -> set[str]:
        if not isinstance(actions, list):
            return set()
        return {str(action).strip().casefold() for action in actions if str(action).strip()}

    def _capture_image_size(self, image: object) -> tuple[int, int]:
        size = getattr(image, "size", None)
        if (
            isinstance(size, tuple)
            and len(size) == 2
            and all(isinstance(value, (int, float)) and value > 0 for value in size)
        ):
            return int(size[0]), int(size[1])
        width = getattr(image, "width", None)
        height = getattr(image, "height", None)
        if isinstance(width, (int, float)) and width > 0 and isinstance(height, (int, float)) and height > 0:
            return int(width), int(height)
        raise ValueError("capture image is missing a usable size")

    def _capture_rect_to_bounds(
        self,
        window: WindowInfo,
        x: int,
        y: int,
        width: int,
        height: int,
        capture_width: int,
        capture_height: int,
    ) -> Bounds:
        scale_x, scale_y = self._capture_scale(window, capture_width, capture_height)
        return Bounds(
            x=window.bounds.x + int(round(x / scale_x)),
            y=window.bounds.y + int(round(y / scale_y)),
            width=max(1, int(round(width / scale_x))),
            height=max(1, int(round(height / scale_y))),
        )

    def _capture_scale(self, window: WindowInfo, capture_width: int, capture_height: int) -> tuple[float, float]:
        window_width = max(int(window.bounds.width), 1)
        window_height = max(int(window.bounds.height), 1)
        scale_x = float(capture_width) / float(window_width) if capture_width > 0 else 1.0
        scale_y = float(capture_height) / float(window_height) if capture_height > 0 else 1.0
        if scale_x <= 0:
            scale_x = 1.0
        if scale_y <= 0:
            scale_y = 1.0
        return scale_x, scale_y

    def _dedupe_elements(self, matches: list[ElementInfo]) -> list[ElementInfo]:
        seen: set[tuple[str, str, int, int, int, int]] = set()
        deduped: list[ElementInfo] = []
        for item in matches:
            key = (
                item.text,
                item.control_type or "",
                int(item.bounds.x),
                int(item.bounds.y),
                int(item.bounds.width),
                int(item.bounds.height),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _iou(self, left_box: tuple[int, int, int, int], right_box: tuple[int, int, int, int]) -> float:
        left_x, left_y, left_w, left_h = left_box
        right_x, right_y, right_w, right_h = right_box
        intersect_left = max(left_x, right_x)
        intersect_top = max(left_y, right_y)
        intersect_right = min(left_x + left_w, right_x + right_w)
        intersect_bottom = min(left_y + left_h, right_y + right_h)
        intersect_width = max(0, intersect_right - intersect_left)
        intersect_height = max(0, intersect_bottom - intersect_top)
        intersection = intersect_width * intersect_height
        if intersection == 0:
            return 0.0
        union = (left_w * left_h) + (right_w * right_h) - intersection
        return intersection / union if union else 0.0

    def _activate_application(self, process_name: str) -> bool:
        try:
            self._run_osascript(f'tell application "{self._escape_applescript(process_name)}" to activate')
        except Exception:
            return False
        return True

    def _focus_specific_window(self, window: WindowInfo) -> bool:
        script = self._build_focus_window_script()
        env = self._window_context_env(window)
        try:
            result = subprocess.run(
                ["osascript", "-l", "AppleScript", "-e", script],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except Exception:
            return False
        return result.stdout.strip().lower() == "true"

    def _window_context_env(self, window: WindowInfo) -> dict[str, str]:
        env = os.environ.copy()
        env["SIMULATEINPUT_PROC_NAME"] = window.process_name or ""
        env["SIMULATEINPUT_WINDOW_TITLE"] = window.title
        env["SIMULATEINPUT_WINDOW_X"] = str(int(window.bounds.x))
        env["SIMULATEINPUT_WINDOW_Y"] = str(int(window.bounds.y))
        env["SIMULATEINPUT_WINDOW_WIDTH"] = str(int(window.bounds.width))
        env["SIMULATEINPUT_WINDOW_HEIGHT"] = str(int(window.bounds.height))
        return env

    def _build_uia_script(self) -> str:
        return r'''
on replace_text(theText, oldString, newString)
    set AppleScript's text item delimiters to oldString
    set textItems to every text item of theText
    set AppleScript's text item delimiters to newString
    set theText to textItems as string
    set AppleScript's text item delimiters to ""
    return theText
end replace_text

on json_escape(theText)
    set theText to my replace_text(theText, "\\", "\\\\")
    set theText to my replace_text(theText, "\"", "\\\"")
    set theText to my replace_text(theText, return, " ")
    set theText to my replace_text(theText, linefeed, " ")
    return theText
end json_escape

on abs_int(valueNumber)
    if valueNumber < 0 then
        return -valueNumber
    end if
    return valueNumber
end abs_int

on format_actions_json(actionList)
    if actionList is "" then
        return ""
    end if
    set previousDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to "|"
    set actionItems to every text item of actionList
    set AppleScript's text item delimiters to previousDelimiters
    set output to ""
    set firstItem to true
    repeat with actionName in actionItems
        set normalizedAction to my json_escape((actionName as text))
        if normalizedAction is not "" then
            if not firstItem then set output to output & ","
            set firstItem to false
            set output to output & "\"" & normalizedAction & "\""
        end if
    end repeat
    return output
end format_actions_json

set procName to system attribute "SIMULATEINPUT_PROC_NAME"
set winTitle to system attribute "SIMULATEINPUT_WINDOW_TITLE"
set targetX to (system attribute "SIMULATEINPUT_WINDOW_X") as integer
set targetY to (system attribute "SIMULATEINPUT_WINDOW_Y") as integer
set targetW to (system attribute "SIMULATEINPUT_WINDOW_WIDTH") as integer
set targetH to (system attribute "SIMULATEINPUT_WINDOW_HEIGHT") as integer
set queryName to system attribute "SIMULATEINPUT_QUERY_NAME"
set queryRole to system attribute "SIMULATEINPUT_QUERY_ROLE"
set queryAid to system attribute "SIMULATEINPUT_QUERY_AID"
set exactFlag to system attribute "SIMULATEINPUT_QUERY_EXACT"
set exactMatch to exactFlag is "1"

tell application "System Events"
    tell process procName
        set targetWindow to missing value
        set bestScore to 2147483647
        repeat with w in windows
            set windowName to ""
            try
                set windowName to (name of w) as text
            end try

            set titlePenalty to 20000
            if windowName is winTitle then
                set titlePenalty to 0
            else if windowName contains winTitle or winTitle contains windowName then
                set titlePenalty to 5000
            end if

            set posX to 0
            set posY to 0
            set sizeW to 0
            set sizeH to 0
            try
                set windowPosition to position of w
                set posX to item 1 of windowPosition
                set posY to item 2 of windowPosition
            end try
            try
                set windowSize to size of w
                set sizeW to item 1 of windowSize
                set sizeH to item 2 of windowSize
            end try
            set score to titlePenalty + (my abs_int(posX - targetX)) + (my abs_int(posY - targetY)) + (my abs_int(sizeW - targetW)) + (my abs_int(sizeH - targetH))
            if targetWindow is missing value or score < bestScore then
                set targetWindow to w
                set bestScore to score
            end if
        end repeat
        if targetWindow is missing value then
            return "[]"
        end if
        set output to "["
        set firstItem to true
        repeat with e in entire contents of targetWindow
            set elementName to ""
            set roleName to ""
            set elementAid to ""
            set posX to 0
            set posY to 0
            set sizeW to 0
            set sizeH to 0
            try
                set elementName to (name of e) as text
            end try
            try
                set roleName to (role of e) as text
            end try
            set subroleName to ""
            try
                set subroleName to (subrole of e) as text
            end try
            try
                set elementAid to (value of attribute "AXIdentifier" of e) as text
            end try
            set className to ""
            if subroleName is not "" then
                set className to subroleName
            else
                set className to roleName
            end if
            try
                set elementPosition to position of e
                set posX to item 1 of elementPosition
                set posY to item 2 of elementPosition
            end try
            try
                set elementSize to size of e
                set sizeW to item 1 of elementSize
                set sizeH to item 2 of elementSize
            end try
            set isVisible to false
            try
                set isVisible to visible of e
            end try
            set isEnabled to true
            try
                set isEnabled to enabled of e
            end try
            set actionList to ""
            try
                set elementActions to actions of e
                set AppleScript's text item delimiters to "|"
                set actionList to elementActions as string
                set AppleScript's text item delimiters to ""
            end try

            set includeItem to true
            if queryName is not "" then
                if exactMatch then
                    if elementName is not queryName then set includeItem to false
                else
                    if elementName does not contain queryName then set includeItem to false
                end if
            end if
            if includeItem and queryRole is not "" then
                if exactMatch then
                    if roleName is not queryRole then set includeItem to false
                else
                    if roleName does not contain queryRole then set includeItem to false
                end if
            end if
            if includeItem and queryAid is not "" then
                if exactMatch then
                    if elementAid is not queryAid then set includeItem to false
                else
                    if elementAid does not contain queryAid then set includeItem to false
                end if
            end if

            if includeItem then
                if not firstItem then set output to output & ","
                set firstItem to false
                set output to output & "{\"id\":\"" & my json_escape(roleName & ":" & elementName & ":" & elementAid & ":" & posX & ":" & posY) & "\",\"text\":\"" & my json_escape(elementName) & "\",\"control_type\":\"" & my json_escape(roleName) & "\",\"class_name\":\"" & my json_escape(className) & "\",\"automation_id\":\"" & my json_escape(elementAid) & "\",\"x\":" & posX & ",\"y\":" & posY & ",\"width\":" & sizeW & ",\"height\":" & sizeH & ",\"visible\":" & isVisible & ",\"enabled\":" & isEnabled & ",\"actions\":[" & my format_actions_json(actionList) & "]}"
            end if
        end repeat
        return output & "]"
    end tell
end tell
'''

    def _build_focus_window_script(self) -> str:
        return r'''
on abs_int(valueNumber)
    if valueNumber < 0 then
        return -valueNumber
    end if
    return valueNumber
end abs_int

set procName to system attribute "SIMULATEINPUT_PROC_NAME"
set winTitle to system attribute "SIMULATEINPUT_WINDOW_TITLE"
set targetX to (system attribute "SIMULATEINPUT_WINDOW_X") as integer
set targetY to (system attribute "SIMULATEINPUT_WINDOW_Y") as integer
set targetW to (system attribute "SIMULATEINPUT_WINDOW_WIDTH") as integer
set targetH to (system attribute "SIMULATEINPUT_WINDOW_HEIGHT") as integer

tell application "System Events"
    tell process procName
        set frontmost to true
        set bestWindow to missing value
        set bestScore to 2147483647
        repeat with w in windows
            set windowName to ""
            try
                set windowName to (name of w) as text
            end try
            set titlePenalty to 20000
            if windowName is winTitle then
                set titlePenalty to 0
            else if windowName contains winTitle or winTitle contains windowName then
                set titlePenalty to 5000
            end if

            set posX to 0
            set posY to 0
            set sizeW to 0
            set sizeH to 0
            try
                set windowPosition to position of w
                set posX to item 1 of windowPosition
                set posY to item 2 of windowPosition
            end try
            try
                set windowSize to size of w
                set sizeW to item 1 of windowSize
                set sizeH to item 2 of windowSize
            end try
            set score to titlePenalty + (my abs_int(posX - targetX)) + (my abs_int(posY - targetY)) + (my abs_int(sizeW - targetW)) + (my abs_int(sizeH - targetH))
            if bestWindow is missing value or score < bestScore then
                set bestWindow to w
                set bestScore to score
            end if
        end repeat
        if bestWindow is missing value then
            return "false"
        end if
        try
            perform action "AXRaise" of bestWindow
        end try
        try
            set value of attribute "AXMain" of bestWindow to true
        end try
        return "true"
    end tell
end tell
'''
