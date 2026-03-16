from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

from simulateinput.core.models import Bounds, ElementInfo, PlatformKind, WindowInfo
from simulateinput.drivers.base import DriverProbe


class LinuxX11Driver:
    platform = PlatformKind.LINUX

    def probe(self) -> DriverProbe:
        if os.name != "posix" or not os.environ.get("DISPLAY"):
            return DriverProbe(
                available=False,
                platform=self.platform,
                message="linux x11 driver requires an active DISPLAY session",
            )
        missing = [tool for tool in ("wmctrl", "xdotool") if shutil.which(tool) is None]
        if missing:
            return DriverProbe(
                available=False,
                platform=self.platform,
                message=f"linux x11 driver requires: {', '.join(missing)}",
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
        ]
        if self._screenshot_command() is not None:
            capabilities.extend(["screenshot", "find_ocr_text", "find_image"])
        return DriverProbe(
            available=True,
            platform=self.platform,
            message="linux x11 driver available through wmctrl/xdotool helpers",
            capabilities=capabilities,
        )

    def list_windows(self) -> list[WindowInfo]:
        result = subprocess.run(
            ["wmctrl", "-lpG"],
            check=True,
            capture_output=True,
            text=True,
        )
        windows: list[WindowInfo] = []
        for raw_line in result.stdout.splitlines():
            parsed = self._parse_wmctrl_line(raw_line)
            if parsed is not None:
                windows.append(parsed)
        return windows

    def focus_window(self, window_id: str) -> bool:
        subprocess.run(["wmctrl", "-ia", str(window_id)], check=True, capture_output=True, text=True)
        return True

    def click(self, x: int, y: int) -> None:
        subprocess.run(["xdotool", "mousemove", "--sync", str(int(x)), str(int(y))], check=True, capture_output=True, text=True)
        subprocess.run(["xdotool", "click", "1"], check=True, capture_output=True, text=True)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, steps: int = 24) -> None:
        subprocess.run(["xdotool", "mousemove", "--sync", str(int(x1)), str(int(y1))], check=True, capture_output=True, text=True)
        subprocess.run(["xdotool", "mousedown", "1"], check=True, capture_output=True, text=True)
        sleep_interval = max(duration_ms, 0) / max(steps, 1) / 1000.0
        for index in range(1, max(steps, 1) + 1):
            progress = index / max(steps, 1)
            next_x = int(round(x1 + ((x2 - x1) * progress)))
            next_y = int(round(y1 + ((y2 - y1) * progress)))
            subprocess.run(["xdotool", "mousemove", "--sync", str(next_x), str(next_y)], check=True, capture_output=True, text=True)
            if sleep_interval > 0:
                time.sleep(sleep_interval)
        subprocess.run(["xdotool", "mouseup", "1"], check=True, capture_output=True, text=True)

    def type_text(self, text: str) -> None:
        subprocess.run(["xdotool", "type", "--delay", "1", "--", text], check=True, capture_output=True, text=True)

    def press_key(self, key: str) -> None:
        subprocess.run(["xdotool", "key", key], check=True, capture_output=True, text=True)

    def hotkey(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("hotkey requires at least one key")
        subprocess.run(["xdotool", "key", "+".join(keys)], check=True, capture_output=True, text=True)

    def clear_text(self) -> None:
        self.hotkey(["ctrl", "a"])
        time.sleep(0.02)
        self.press_key("Delete")

    def screenshot_window(self, window_id: str, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        command = self._screenshot_command()
        if command is None:
            raise RuntimeError("linux x11 screenshot requires import, gnome-screenshot, or scrot")
        if command == "import":
            subprocess.run(["import", "-window", str(window_id), str(output)], check=True, capture_output=True, text=True)
        elif command == "gnome-screenshot":
            self.focus_window(window_id)
            time.sleep(0.2)
            subprocess.run(["gnome-screenshot", "-w", "-f", str(output)], check=True, capture_output=True, text=True)
        elif command == "scrot":
            self.focus_window(window_id)
            time.sleep(0.2)
            subprocess.run(["scrot", "-u", str(output)], check=True, capture_output=True, text=True)
        return str(output)

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list[ElementInfo]:
        window = next((item for item in self.list_windows() if item.window_id == str(window_id)), None)
        if window is None:
            return []
        lowered = text.casefold()
        haystack = window.title.casefold()
        matched = haystack == lowered if exact else lowered in haystack
        if not matched:
            return []
        return [
            ElementInfo(
                element_id=f"x11-window-{window.window_id}",
                window_id=window.window_id,
                platform=self.platform,
                text=window.title,
                bounds=window.bounds,
                class_name=None,
                control_type="x11-window",
                source="x11-title",
                confidence=1.0 if exact else 0.8,
            )
        ]
        try:
            matches.extend(self.find_uia(window_id, name=text, exact=exact, max_results=20))
        except Exception:
            pass
        deduped: list[ElementInfo] = []
        seen: set[tuple[str, str, int, int, int, int]] = set()
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
        window = next((item for item in self.list_windows() if item.window_id == str(window_id)), None)
        if window is None:
            return []
        python3 = shutil.which("python3") or shutil.which("python")
        if python3 is None:
            raise RuntimeError("linux x11 UIA-like lookup requires python3 with pyatspi")
        script = textwrap.dedent(
            """
            import json
            import os
            import sys

            try:
                import pyatspi
            except Exception:
                print("[]")
                raise SystemExit(0)

            TARGET_X = int(os.environ["SIM_X"])
            TARGET_Y = int(os.environ["SIM_Y"])
            TARGET_W = int(os.environ["SIM_W"])
            TARGET_H = int(os.environ["SIM_H"])
            QUERY_NAME = os.environ.get("SIM_QUERY_NAME", "")
            QUERY_ROLE = os.environ.get("SIM_QUERY_ROLE", "")
            QUERY_AID = os.environ.get("SIM_QUERY_AID", "")
            EXACT = os.environ.get("SIM_QUERY_EXACT", "0") == "1"
            LIMIT = int(os.environ.get("SIM_QUERY_LIMIT", "20"))

            def inside(bounds):
                x, y, w, h = bounds
                return (
                    x >= TARGET_X and y >= TARGET_Y and
                    x + w <= TARGET_X + TARGET_W and
                    y + h <= TARGET_Y + TARGET_H
                )

            def matches(candidate, query):
                if not query:
                    return True
                candidate = (candidate or "").strip()
                query = query.strip()
                if EXACT:
                    return candidate.casefold() == query.casefold()
                return query.casefold() in candidate.casefold()

            def collect(node, out):
                if len(out) >= LIMIT:
                    return
                name = getattr(node, "name", "") or ""
                role = ""
                try:
                    role = node.getRoleName() or ""
                except Exception:
                    pass
                attrs = {}
                try:
                    for item in node.getAttributes() or []:
                        if ":" in item:
                            key, value = item.split(":", 1)
                            attrs[key] = value
                except Exception:
                    pass
                aid = attrs.get("automation_id") or attrs.get("id") or attrs.get("identifier") or ""
                try:
                    component = node.queryComponent()
                    extents = component.getExtents(pyatspi.XY_SCREEN)
                    bounds = (int(extents.x), int(extents.y), int(extents.width), int(extents.height))
                except Exception:
                    bounds = None
                if bounds and inside(bounds) and matches(name, QUERY_NAME) and matches(role, QUERY_ROLE) and matches(aid, QUERY_AID):
                    out.append(
                        {
                            "id": str(id(node)),
                            "text": name,
                            "control_type": role,
                            "automation_id": aid,
                            "x": bounds[0],
                            "y": bounds[1],
                            "width": bounds[2],
                            "height": bounds[3],
                        }
                    )
                try:
                    for child in node:
                        collect(child, out)
                except Exception:
                    return

            results = []
            desktop = pyatspi.Registry.getDesktop(0)
            for app in desktop:
                collect(app, results)
                if len(results) >= LIMIT:
                    break
            print(json.dumps(results[:LIMIT]))
            """
        )
        env = os.environ.copy()
        env.update(
            {
                "SIM_X": str(window.bounds.x),
                "SIM_Y": str(window.bounds.y),
                "SIM_W": str(window.bounds.width),
                "SIM_H": str(window.bounds.height),
                "SIM_QUERY_NAME": name or "",
                "SIM_QUERY_ROLE": control_type or "",
                "SIM_QUERY_AID": automation_id or "",
                "SIM_QUERY_EXACT": "1" if exact else "0",
                "SIM_QUERY_LIMIT": str(max_results),
            }
        )
        result = subprocess.run([python3, "-c", script], check=True, capture_output=True, text=True, env=env)
        payload = result.stdout.strip() or "[]"
        parsed = json.loads(payload)
        return [
            ElementInfo(
                element_id=str(item.get("id") or f"x11-uia-{index}"),
                window_id=str(window_id),
                platform=self.platform,
                text=str(item.get("text") or ""),
                bounds=Bounds(
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=int(item.get("width", 0)),
                    height=int(item.get("height", 0)),
                ),
                control_type=item.get("control_type"),
                automation_id=item.get("automation_id"),
                source="at-spi",
                confidence=1.0 if exact else 0.9,
            )
            for index, item in enumerate(parsed[:max_results])
        ]

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

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            self.screenshot_window(window_id, str(temp_path))
            image = Image.open(temp_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            window = next((item for item in self.list_windows() if item.window_id == str(window_id)), None)
            if window is None:
                return []
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
                candidate = normalized.casefold()
                matched = candidate == lowered if exact else lowered in candidate
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
            window = next((item for item in self.list_windows() if item.window_id == str(window_id)), None)
            if window is None:
                return []
            matches: list[ElementInfo] = []
            accepted: list[tuple[int, int, int, int]] = []
            locations: list[tuple[float, int, int, int, int]] = []
            original_height, original_width = template.shape[:2]
            for scale in (0.75, 0.9, 1.0, 1.1, 1.25):
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
                        bounds=Bounds(
                            x=window.bounds.x + x,
                            y=window.bounds.y + y,
                            width=width,
                            height=height,
                        ),
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

    def _parse_wmctrl_line(self, raw_line: str) -> WindowInfo | None:
        parts = raw_line.split(None, 8)
        if len(parts) < 9:
            return None
        window_id, _desktop, pid, x, y, width, height, _host, title = parts
        title = title.strip()
        if not title:
            return None
        return WindowInfo(
            window_id=window_id,
            title=title,
            platform=self.platform,
            bounds=Bounds(x=int(x), y=int(y), width=int(width), height=int(height)),
            process_id=int(pid),
            is_visible=True,
        )

    def _screenshot_command(self) -> str | None:
        for command in ("import", "gnome-screenshot", "scrot"):
            if shutil.which(command):
                return command
        return None

    def _resolve_tesseract_cmd(self) -> str | None:
        configured = os.environ.get("TESSERACT_CMD")
        if configured and Path(configured).exists():
            return configured
        return shutil.which("tesseract")

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
