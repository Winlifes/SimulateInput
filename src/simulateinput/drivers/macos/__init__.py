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
        capabilities = [
            "probe",
            "list_windows",
            "attach_window",
            "find_text",
            "find_uia",
            "click",
            "drag",
            "type_text",
            "press_key",
            "hotkey",
            "clear_text",
            "screenshot",
        ]
        if self._resolve_tesseract_cmd() is not None:
            capabilities.append("find_ocr_text")
        try:
            import cv2  # noqa: F401
            from PIL import Image  # noqa: F401
            capabilities.append("find_image")
        except ModuleNotFoundError:
            pass
        return DriverProbe(
            available=True,
            platform=self.platform,
            message="macOS driver available with Quartz input, window enumeration, and accessibility lookup",
            capabilities=capabilities,
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
        for window in self.list_windows():
            if window.window_id != str(window_id) or not window.process_name:
                continue
            self._run_osascript(f'tell application "{self._escape_applescript(window.process_name)}" to activate')
            return True
        return False

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
        env = os.environ.copy()
        env["SIMULATEINPUT_PROC_NAME"] = window.process_name
        env["SIMULATEINPUT_WINDOW_TITLE"] = window.title
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
        matches: list[ElementInfo] = []
        for item in parsed[:max_results]:
            matches.append(
                ElementInfo(
                    element_id=str(item.get("id") or f"mac-ax-{len(matches)}"),
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
                    confidence=1.0 if exact else 0.95,
                )
            )
        return matches

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
                matches.append(
                    ElementInfo(
                        element_id=f"ocr-{window_id}-{index}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=normalized,
                        bounds=Bounds(
                            x=window.bounds.x + int(data["left"][index]),
                            y=window.bounds.y + int(data["top"][index]),
                            width=int(data["width"][index]),
                            height=int(data["height"][index]),
                        ),
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
            screen = cv2.cvtColor(np.array(Image.open(temp_path).convert("RGB")), cv2.COLOR_RGB2BGR)
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
                matches.append(
                    ElementInfo(
                        element_id=f"img-{window_id}-{len(matches)}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=template_path.name,
                        bounds=Bounds(x=window.bounds.x + x, y=window.bounds.y + y, width=width, height=height),
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
        subprocess.run(["screencapture", "-x", "-l", str(window_id), str(output)], check=True, capture_output=True, text=True)
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

set procName to system attribute "SIMULATEINPUT_PROC_NAME"
set winTitle to system attribute "SIMULATEINPUT_WINDOW_TITLE"
set queryName to system attribute "SIMULATEINPUT_QUERY_NAME"
set queryRole to system attribute "SIMULATEINPUT_QUERY_ROLE"
set queryAid to system attribute "SIMULATEINPUT_QUERY_AID"
set exactFlag to system attribute "SIMULATEINPUT_QUERY_EXACT"
set exactMatch to exactFlag is "1"

tell application "System Events"
    tell process procName
        set targetWindow to first window whose name is winTitle
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
            try
                set elementAid to (value of attribute "AXIdentifier" of e) as text
            end try
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
                set output to output & "{\"id\":\"" & my json_escape(roleName & ":" & elementName & ":" & elementAid) & "\",\"text\":\"" & my json_escape(elementName) & "\",\"control_type\":\"" & my json_escape(roleName) & "\",\"automation_id\":\"" & my json_escape(elementAid) & "\",\"x\":" & posX & ",\"y\":" & posY & ",\"width\":" & sizeW & ",\"height\":" & sizeH & "}"
            end if
        end repeat
        return output & "]"
    end tell
end tell
'''
