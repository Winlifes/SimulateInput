from __future__ import annotations

from simulateinput.core.models import ActionResult


def build_drag_result(source: str, destination: str) -> ActionResult:
    return ActionResult(
        ok=False,
        code="NOT_IMPLEMENTED",
        message=f"drag action is not implemented yet from '{source}' to '{destination}'",
    )
