from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from simulateinput.core.models import Bounds, ElementInfo, PlatformKind
from simulateinput.drivers.base import DriverProbe


class LinuxWaylandDriver:
    platform = PlatformKind.LINUX

    def probe(self) -> DriverProbe:
        if os.name != "posix" or not os.environ.get("WAYLAND_DISPLAY"):
            return DriverProbe(
                available=False,
                platform=self.platform,
                message="linux wayland driver requires an active WAYLAND_DISPLAY session",
            )
        capabilities = ["probe"]
        helpers: list[str] = []
        if shutil.which("ydotool"):
            capabilities.extend(["click", "drag", "press_key", "hotkey", "clear_text"])
            helpers.append("ydotool")
        elif shutil.which("wtype"):
            capabilities.extend(["type_text", "press_key", "hotkey"])
            helpers.append("wtype")
        if shutil.which("grim"):
            capabilities.extend(["screenshot", "find_ocr_text", "find_image"])
            helpers.append("grim")
        message = "linux wayland compatibility layer available"
        if helpers:
            message += f" using helpers: {', '.join(helpers)}"
        else:
            message += "; install ydotool/wtype and grim for usable actions"
        return DriverProbe(
            available=bool(helpers),
            platform=self.platform,
            message=message,
            capabilities=capabilities,
        )

    def list_windows(self) -> list:
        raise RuntimeError("generic Wayland window enumeration is not supported; use compositor-specific integration")

    def focus_window(self, window_id: str) -> bool:
        raise RuntimeError("generic Wayland window focusing is not supported; use compositor-specific integration")

    def click(self, x: int, y: int) -> None:
        if not shutil.which("ydotool"):
            raise RuntimeError("Wayland click requires ydotool")
        subprocess.run(["ydotool", "mousemove", "--absolute", str(int(x)), str(int(y))], check=True, capture_output=True, text=True)
        subprocess.run(["ydotool", "click", "0xC0"], check=True, capture_output=True, text=True)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, steps: int = 24) -> None:
        raise RuntimeError("generic Wayland drag is not implemented; use compositor-specific integration")

    def type_text(self, text: str) -> None:
        if shutil.which("wtype"):
            subprocess.run(["wtype", text], check=True, capture_output=True, text=True)
            return
        raise RuntimeError("Wayland text input requires wtype")

    def press_key(self, key: str) -> None:
        if shutil.which("wtype"):
            subprocess.run(["wtype", "-k", key], check=True, capture_output=True, text=True)
            return
        raise RuntimeError("Wayland key input requires wtype")

    def hotkey(self, keys: list[str]) -> None:
        raise RuntimeError("generic Wayland hotkeys are not implemented; use compositor-specific integration")

    def clear_text(self) -> None:
        raise RuntimeError("generic Wayland clear_text is not implemented; use compositor-specific integration")

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        if not shutil.which("grim"):
            raise RuntimeError("Wayland screenshots require grim")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["grim", str(output)], check=True, capture_output=True, text=True)
        return str(output)

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
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            self.screenshot_window(window_id, str(temp_path))
            image = Image.open(temp_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
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
                        element_id=f"ocr-wayland-{index}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=normalized,
                        bounds=Bounds(
                            x=int(data["left"][index]),
                            y=int(data["top"][index]),
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
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            template_height, template_width = template.shape[:2]
            matches: list[ElementInfo] = []
            accepted: list[tuple[int, int, int, int]] = []
            ys, xs = (result >= threshold).nonzero()
            candidates = sorted(
                ((float(result[y, x]), int(x), int(y)) for y, x in zip(ys, xs)),
                reverse=True,
                key=lambda item: item[0],
            )
            for score, x, y in candidates:
                box = (x, y, template_width, template_height)
                if any(self._iou(box, other) >= 0.35 for other in accepted):
                    continue
                accepted.append(box)
                matches.append(
                    ElementInfo(
                        element_id=f"img-wayland-{len(matches)}",
                        window_id=str(window_id),
                        platform=self.platform,
                        text=template_path.name,
                        bounds=Bounds(x=x, y=y, width=template_width, height=template_height),
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
