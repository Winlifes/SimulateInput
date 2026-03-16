from __future__ import annotations

from simulateinput.locators.base import LocateResult
from simulateinput.core.models import TargetKind


def locate_text(text: str) -> LocateResult:
    return LocateResult(
        found=False,
        kind=TargetKind.TEXT,
        message=f"ocr locator is not implemented yet for '{text}'",
    )
