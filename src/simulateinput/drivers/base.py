from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from simulateinput.core.models import PlatformKind


@dataclass(slots=True)
class DriverProbe:
    available: bool
    platform: PlatformKind
    message: str = ""
    capabilities: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class PlatformDriver(Protocol):
    platform: PlatformKind

    def probe(self) -> DriverProbe:
        ...

    def list_windows(self) -> list:
        ...

    def focus_window(self, window_id: str) -> bool:
        ...

    def find_text(self, window_id: str, text: str, exact: bool = False) -> list:
        ...

    def find_uia(
        self,
        window_id: str,
        name: str | None = None,
        control_type: str | None = None,
        automation_id: str | None = None,
        exact: bool = False,
        max_results: int = 20,
    ) -> list:
        ...

    def find_ocr_text(
        self,
        window_id: str,
        text: str,
        exact: bool = False,
        confidence_threshold: float = 0.0,
    ) -> list:
        ...

    def find_image(
        self,
        window_id: str,
        image_path: str,
        threshold: float = 0.9,
        max_results: int = 5,
    ) -> list:
        ...
