from __future__ import annotations

from simulateinput.locators.base import LocateResult
from simulateinput.core.models import TargetKind


def locate_uia(name: str) -> LocateResult:
    return LocateResult(
        found=False,
        kind=TargetKind.ELEMENT,
        message=f"uia locator is not implemented yet for '{name}'",
    )
