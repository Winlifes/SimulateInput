from __future__ import annotations

from simulateinput.locators.base import LocateResult
from simulateinput.core.models import TargetKind


def locate_selector(selector: str) -> LocateResult:
    return LocateResult(
        found=False,
        kind=TargetKind.ELEMENT,
        message=f"selector locator is not implemented yet for '{selector}'",
    )
