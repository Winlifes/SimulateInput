from __future__ import annotations

import ctypes
import os
import shutil
import time
import zlib
from ctypes import wintypes
from pathlib import Path

from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo
from simulateinput.drivers.base import DriverProbe

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
SW_RESTORE = 9
INPUT_KEYBOARD = 1
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
VK_CODE_MAP = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "meta": 0x5B,
    "win": 0x5B,
    "cmd": 0x5B,
}
for index in range(1, 13):
    VK_CODE_MAP[f"f{index}"] = 0x6F + index


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


class WindowsDriver:
    platform = PlatformKind.WINDOWS

    def probe(self) -> DriverProbe:
        available = hasattr(ctypes, "windll")
        return DriverProbe(
            available=available,
            platform=self.platform,
            message=(
                "windows driver available for window enumeration and basic input injection"
                if available
                else "windows driver is unavailable on this platform"
            ),
            capabilities=[
                "probe",
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
            if available
            else [],
        )

    def list_windows(self) -> list[WindowInfo]:
        user32 = self._user32()
        windows: list[WindowInfo] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            title = title_buffer.value.strip()
            if not title:
                return True

            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            windows.append(
                WindowInfo(
                    window_id=str(hwnd),
                    title=title,
                    platform=self.platform,
                    bounds=Bounds(
                        x=int(rect.left),
                        y=int(rect.top),
                        width=int(rect.right - rect.left),
                        height=int(rect.bottom - rect.top),
                    ),
                    process_id=int(pid.value),
                    is_visible=True,
                )
            )
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        return windows

    def focus_window(self, window_id: str) -> bool:
        user32 = self._user32()
        hwnd = int(window_id)
        user32.ShowWindow(hwnd, SW_RESTORE)
        return bool(user32.SetForegroundWindow(hwnd))

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list[ElementInfo]:
        user32 = self._user32()
        query = text.strip()
        if not query:
            raise ValueError("text query must not be empty")

        hwnd = int(window_id)
        matches: list[ElementInfo] = []
        lowered_query = query.casefold()

        def add_match(candidate_hwnd: int) -> None:
            title = self._get_window_text(candidate_hwnd)
            if not title:
                return
            lowered_title = title.casefold()
            is_match = lowered_title == lowered_query if exact else lowered_query in lowered_title
            if not is_match:
                return
            bounds = self._get_window_bounds(candidate_hwnd)
            if bounds is None:
                return
            matches.append(
                ElementInfo(
                    element_id=str(candidate_hwnd),
                    window_id=str(hwnd),
                    platform=self.platform,
                    text=title,
                    bounds=bounds,
                    class_name=self._get_class_name(candidate_hwnd),
                    control_type="win32-child",
                    source="win32-text",
                    confidence=1.0 if exact else 0.85,
                )
            )

        add_match(hwnd)

        enum_child_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(child_hwnd: int, lparam: int) -> bool:
            if not user32.IsWindowVisible(child_hwnd):
                return True
            add_match(child_hwnd)
            return True

        user32.EnumChildWindows(hwnd, enum_child_proc(callback), 0)
        return matches

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
        try:
            from pywinauto import Desktop
        except ModuleNotFoundError as exc:
            raise RuntimeError("pywinauto is required for UIA lookup") from exc

        target_handle = int(window_id)
        desktop = Desktop(backend="uia")
        wrapper = desktop.window(handle=target_handle)
        descendants = [wrapper] + list(wrapper.descendants())

        def normalize(value: str | None) -> str:
            return (value or "").strip()

        def matches_filter(candidate_text: str, query: str | None) -> bool:
            if query is None:
                return True
            normalized_query = normalize(query)
            normalized_text = normalize(candidate_text)
            if exact:
                return normalized_text.casefold() == normalized_query.casefold()
            return normalized_query.casefold() in normalized_text.casefold()

        results: list[ElementInfo] = []
        for candidate in descendants:
            info = candidate.element_info
            candidate_name = normalize(getattr(info, "name", ""))
            candidate_control_type = normalize(getattr(info, "control_type", ""))
            candidate_automation_id = normalize(getattr(info, "automation_id", ""))
            if not matches_filter(candidate_name, name):
                continue
            if control_type is not None and not matches_filter(candidate_control_type, control_type):
                continue
            if automation_id is not None and not matches_filter(candidate_automation_id, automation_id):
                continue

            rect = getattr(info, "rectangle", None)
            if rect is None:
                continue
            results.append(
                ElementInfo(
                    element_id=str(getattr(info, "handle", None) or id(info)),
                    window_id=window_id,
                    platform=self.platform,
                    text=candidate_name or candidate_control_type or candidate_automation_id,
                    bounds=Bounds(
                        x=int(rect.left),
                        y=int(rect.top),
                        width=int(rect.right - rect.left),
                        height=int(rect.bottom - rect.top),
                    ),
                    class_name=normalize(getattr(info, "class_name", "")) or None,
                    control_type=candidate_control_type or None,
                    automation_id=candidate_automation_id or None,
                    source="uia",
                    confidence=1.0 if exact else 0.95,
                )
            )
            if len(results) >= max_results:
                break
        return results

    def find_ocr_text(
        self,
        window_id: str,
        text: str,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> list[ElementInfo]:
        query = text.strip()
        if not query:
            raise ValueError("ocr text query must not be empty")
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

        bounds, image = self._capture_window_image(window_id)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        lowered_query = query.casefold()
        matches: list[ElementInfo] = []
        for index, candidate_text in enumerate(data.get("text", [])):
            normalized_text = str(candidate_text).strip()
            if not normalized_text:
                continue
            confidence_raw = data.get("conf", ["-1"])[index]
            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = -1.0
            if confidence < confidence_threshold:
                continue
            comparison = normalized_text.casefold()
            is_match = comparison == lowered_query if exact else lowered_query in comparison
            if not is_match:
                continue
            left = int(data["left"][index]) + bounds.x
            top = int(data["top"][index]) + bounds.y
            width = int(data["width"][index])
            height = int(data["height"][index])
            matches.append(
                ElementInfo(
                    element_id=f"ocr-{window_id}-{index}",
                    window_id=window_id,
                    platform=self.platform,
                    text=normalized_text,
                    bounds=Bounds(x=left, y=top, width=width, height=height),
                    control_type="ocr-text",
                    source="ocr",
                    confidence=max(confidence / 100.0, 0.0),
                )
            )
        return matches

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
        except ModuleNotFoundError as exc:
            raise RuntimeError("opencv-python-headless and numpy are required for image lookup") from exc

        template_path = Path(image_path)
        if not template_path.exists():
            raise ValueError(f"image template not found: {image_path}")

        bounds, image = self._capture_window_image(window_id)
        screen = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template is None:
            raise ValueError(f"failed to read image template: {image_path}")

        locations: list[tuple[float, int, int, int, int]] = []
        original_height, original_width = template.shape[:2]
        scales = [0.75, 0.9, 1.0, 1.1, 1.25]
        for scale in scales:
            scaled_width = max(1, int(round(original_width * scale)))
            scaled_height = max(1, int(round(original_height * scale)))
            if scaled_width > screen.shape[1] or scaled_height > screen.shape[0]:
                continue
            if scale == 1.0:
                scaled_template = template
            else:
                scaled_template = cv2.resize(template, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
            result = cv2.matchTemplate(screen, scaled_template, cv2.TM_CCOEFF_NORMED)
            for y, x in zip(*((result >= threshold).nonzero())):
                score = float(result[y, x])
                locations.append((score, int(x), int(y), int(scaled_width), int(scaled_height)))
        locations.sort(reverse=True, key=lambda item: item[0])

        matches: list[ElementInfo] = []
        accepted_boxes: list[tuple[int, int, int, int]] = []
        for score, x, y, width, height in locations:
            candidate_box = (x, y, width, height)
            if any(self._intersection_over_union(candidate_box, existing) >= 0.35 for existing in accepted_boxes):
                continue
            accepted_boxes.append(candidate_box)
            matches.append(
                ElementInfo(
                    element_id=f"img-{window_id}-{len(matches)}",
                    window_id=window_id,
                    platform=self.platform,
                    text=template_path.name,
                    bounds=Bounds(
                        x=bounds.x + x,
                        y=bounds.y + y,
                        width=int(width),
                        height=int(height),
                    ),
                    control_type="image-template",
                    source="image",
                    confidence=score,
                )
            )
            if len(matches) >= max_results:
                break
        return matches

    def click(self, x: int, y: int) -> None:
        user32 = self._user32()
        if not user32.SetCursorPos(int(x), int(y)):
            raise RuntimeError(f"failed to move cursor to ({x}, {y})")
        time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, steps: int = 24) -> None:
        user32 = self._user32()
        if not user32.SetCursorPos(int(x1), int(y1)):
            raise RuntimeError(f"failed to move cursor to ({x1}, {y1})")

        time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        sleep_interval = max(duration_ms, 0) / max(steps, 1) / 1000.0

        for index in range(1, max(steps, 1) + 1):
            progress = index / max(steps, 1)
            next_x = round(x1 + ((x2 - x1) * progress))
            next_y = round(y1 + ((y2 - y1) * progress))
            user32.SetCursorPos(int(next_x), int(next_y))
            if sleep_interval > 0:
                time.sleep(sleep_interval)

        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def type_text(self, text: str) -> None:
        user32 = self._user32()
        for char in text:
            unicode_codepoint = ord(char)
            inputs = (INPUT * 2)()
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].union.ki = KEYBDINPUT(0, unicode_codepoint, KEYEVENTF_UNICODE, 0, 0)
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].union.ki = KEYBDINPUT(0, unicode_codepoint, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)

            sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            if sent != 2:
                raise RuntimeError(f"failed to inject character {char!r}")
            time.sleep(0.005)

    def press_key(self, key: str) -> None:
        virtual_key = self._resolve_virtual_key(key)
        self._send_virtual_key(virtual_key, key_up=False)
        time.sleep(0.01)
        self._send_virtual_key(virtual_key, key_up=True)

    def hotkey(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("hotkey requires at least one key")
        virtual_keys = [self._resolve_virtual_key(key) for key in keys]
        for virtual_key in virtual_keys[:-1]:
            self._send_virtual_key(virtual_key, key_up=False)
            time.sleep(0.01)
        self._send_virtual_key(virtual_keys[-1], key_up=False)
        time.sleep(0.01)
        self._send_virtual_key(virtual_keys[-1], key_up=True)
        for virtual_key in reversed(virtual_keys[:-1]):
            time.sleep(0.01)
            self._send_virtual_key(virtual_key, key_up=True)

    def clear_text(self) -> None:
        self.hotkey(["ctrl", "a"])
        time.sleep(0.02)
        self.press_key("delete")

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        _, _, width, height, data = self._capture_window_bgra(window_id)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        suffix = output.suffix.lower()
        if suffix == ".png":
            self._write_png(output, width, height, data)
        elif suffix == ".bmp":
            self._write_bmp(output, width, height, data)
        else:
            raise ValueError("screenshot output must use .png or .bmp")
        return str(output)

    def _user32(self):  # type: ignore[no-untyped-def]
        if not hasattr(ctypes, "windll"):
            raise RuntimeError("windows user32 API is unavailable on this platform")
        return ctypes.windll.user32

    def _gdi32(self):  # type: ignore[no-untyped-def]
        if not hasattr(ctypes, "windll"):
            raise RuntimeError("windows gdi32 API is unavailable on this platform")
        return ctypes.windll.gdi32

    def _capture_window_bgra(self, window_id: str) -> tuple[int, int, int, int, bytes]:
        hwnd = int(window_id)
        user32 = self._user32()
        gdi32 = self._gdi32()

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError(f"failed to get rect for window {window_id}")

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"window {window_id} has invalid bounds {width}x{height}")

        hwnd_dc = user32.GetWindowDC(hwnd)
        if not hwnd_dc:
            raise RuntimeError(f"failed to get device context for window {window_id}")

        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        if not mem_dc:
            user32.ReleaseDC(hwnd, hwnd_dc)
            raise RuntimeError("failed to create compatible device context")

        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
        if not bitmap:
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)
            raise RuntimeError("failed to create compatible bitmap")

        previous = gdi32.SelectObject(mem_dc, bitmap)
        if not previous:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)
            raise RuntimeError("failed to select bitmap into device context")

        try:
            if not gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, SRCCOPY):
                raise RuntimeError("failed to capture window bitmap")

            bitmap_info = BITMAPINFO()
            bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bitmap_info.bmiHeader.biWidth = width
            bitmap_info.bmiHeader.biHeight = -height
            bitmap_info.bmiHeader.biPlanes = 1
            bitmap_info.bmiHeader.biBitCount = 32
            bitmap_info.bmiHeader.biCompression = BI_RGB

            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)
            scan_lines = gdi32.GetDIBits(
                mem_dc,
                bitmap,
                0,
                height,
                buffer,
                ctypes.byref(bitmap_info),
                DIB_RGB_COLORS,
            )
            if scan_lines != height:
                raise RuntimeError("failed to read captured bitmap data")
            return int(rect.left), int(rect.top), width, height, bytes(buffer.raw)
        finally:
            gdi32.SelectObject(mem_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

    def _capture_window_image(self, window_id: str):  # type: ignore[no-untyped-def]
        try:
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise RuntimeError("pillow is required for in-memory image capture") from exc
        left, top, width, height, data = self._capture_window_bgra(window_id)
        image = Image.frombuffer("RGBA", (width, height), data, "raw", "BGRA", 0, 1).convert("RGB")
        return Bounds(x=left, y=top, width=width, height=height), image

    def _write_png(self, output: Path, width: int, height: int, bgra: bytes) -> None:
        rows: list[bytes] = []
        stride = width * 4
        for row_index in range(height):
            row = bgra[row_index * stride : (row_index + 1) * stride]
            rgb = bytearray(width * 3)
            for pixel_index in range(width):
                source = pixel_index * 4
                target = pixel_index * 3
                rgb[target] = row[source + 2]
                rgb[target + 1] = row[source + 1]
                rgb[target + 2] = row[source]
            rows.append(b"\x00" + bytes(rgb))

        payload = b"".join(rows)
        compressed = zlib.compress(payload)
        png = bytearray()
        png.extend(b"\x89PNG\r\n\x1a\n")
        png.extend(self._png_chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"))
        png.extend(self._png_chunk(b"IDAT", compressed))
        png.extend(self._png_chunk(b"IEND", b""))
        output.write_bytes(bytes(png))

    def _write_bmp(self, output: Path, width: int, height: int, bgra: bytes) -> None:
        pixel_data_size = width * height * 4
        file_header_size = 14
        info_header_size = 40
        offset = file_header_size + info_header_size
        file_size = offset + pixel_data_size

        file_header = b"BM" + file_size.to_bytes(4, "little") + b"\x00\x00\x00\x00" + offset.to_bytes(4, "little")
        info_header = (
            info_header_size.to_bytes(4, "little")
            + width.to_bytes(4, "little", signed=True)
            + (-height).to_bytes(4, "little", signed=True)
            + (1).to_bytes(2, "little")
            + (32).to_bytes(2, "little")
            + (0).to_bytes(4, "little")
            + pixel_data_size.to_bytes(4, "little")
            + (2835).to_bytes(4, "little", signed=True)
            + (2835).to_bytes(4, "little", signed=True)
            + (0).to_bytes(4, "little")
            + (0).to_bytes(4, "little")
        )
        output.write_bytes(file_header + info_header + bgra)

    def _png_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        length = len(data).to_bytes(4, "big")
        checksum = zlib.crc32(chunk_type)
        checksum = zlib.crc32(data, checksum)
        return length + chunk_type + data + checksum.to_bytes(4, "big")

    def _get_window_text(self, hwnd: int) -> str:
        user32 = self._user32()
        length = user32.GetWindowTextLengthW(hwnd)
        if length < 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()

    def _get_class_name(self, hwnd: int) -> str:
        user32 = self._user32()
        buffer = ctypes.create_unicode_buffer(256)
        copied = user32.GetClassNameW(hwnd, buffer, 256)
        if copied <= 0:
            return ""
        return buffer.value

    def _get_window_bounds(self, hwnd: int) -> Bounds | None:
        user32 = self._user32()
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return Bounds(
            x=int(rect.left),
            y=int(rect.top),
            width=int(rect.right - rect.left),
            height=int(rect.bottom - rect.top),
        )

    def _resolve_virtual_key(self, key: str) -> int:
        normalized = key.strip().lower()
        if not normalized:
            raise ValueError("key must not be empty")
        if normalized in VK_CODE_MAP:
            return VK_CODE_MAP[normalized]
        if len(normalized) == 1 and normalized.isalpha():
            return ord(normalized.upper())
        if len(normalized) == 1 and normalized.isdigit():
            return ord(normalized)
        raise ValueError(f"unsupported key: {key}")

    def _send_virtual_key(self, virtual_key: int, key_up: bool) -> None:
        user32 = self._user32()
        inputs = (INPUT * 1)()
        flags = KEYEVENTF_KEYUP if key_up else 0
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki = KEYBDINPUT(virtual_key, 0, flags, 0, 0)
        sent = user32.SendInput(1, inputs, ctypes.sizeof(INPUT))
        if sent != 1:
            state = "release" if key_up else "press"
            raise RuntimeError(f"failed to {state} virtual key {virtual_key}")

    def _resolve_tesseract_cmd(self) -> str | None:
        configured = os.environ.get("TESSERACT_CMD")
        if configured and Path(configured).exists():
            return configured
        discovered = shutil.which("tesseract")
        if discovered:
            return discovered
        default_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if default_path.exists():
            return str(default_path)
        return None

    def _intersection_over_union(
        self,
        left_box: tuple[int, int, int, int],
        right_box: tuple[int, int, int, int],
    ) -> float:
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
        left_area = left_w * left_h
        right_area = right_w * right_h
        union = left_area + right_area - intersection
        return intersection / union if union else 0.0
