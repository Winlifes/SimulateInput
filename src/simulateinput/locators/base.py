from __future__ import annotations

from dataclasses import dataclass

from simulateinput.core.models import Bounds, TargetKind


@dataclass(slots=True)
class LocateResult:
    found: bool
    kind: TargetKind
    bounds: Bounds | None = None
    confidence: float | None = None
    message: str = ""
