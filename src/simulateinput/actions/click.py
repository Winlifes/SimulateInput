from __future__ import annotations

from simulateinput.core.models import ActionResult


def build_click_result(target: str) -> ActionResult:
    return ActionResult(
        ok=False,
        code="NOT_IMPLEMENTED",
        message=f"click action is not implemented yet for target '{target}'",
    )
