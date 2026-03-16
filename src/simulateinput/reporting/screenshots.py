from __future__ import annotations

from pathlib import Path


def build_screenshot_path(artifacts_dir: str, label: str) -> Path:
    return Path(artifacts_dir) / f"{label}.png"
