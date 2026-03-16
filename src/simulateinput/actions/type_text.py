from __future__ import annotations

from simulateinput.core.models import ActionResult


def build_type_text_result(text: str) -> ActionResult:
    return ActionResult(
        ok=False,
        code="NOT_IMPLEMENTED",
        message=f"type_text action is not implemented yet for {len(text)} characters",
    )
