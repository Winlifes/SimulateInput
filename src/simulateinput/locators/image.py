from __future__ import annotations

from simulateinput.locators.base import LocateResult
from simulateinput.core.models import TargetKind


def locate_image(image_path: str) -> LocateResult:
    return LocateResult(
        found=False,
        kind=TargetKind.IMAGE,
        message=f"image locator is not implemented yet for '{image_path}'",
    )
