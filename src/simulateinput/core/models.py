from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


class PlatformKind(StrEnum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    BROWSER = "browser"
    UNKNOWN = "unknown"


class TargetKind(StrEnum):
    WINDOW = "window"
    ELEMENT = "element"
    IMAGE = "image"
    TEXT = "text"
    COORDINATE = "coordinate"
    PAGE = "page"


class ArtifactKind(StrEnum):
    SCREENSHOT = "screenshot"
    REPORT = "report"
    LOG = "log"
    TRACE = "trace"
    VIDEO = "video"
    DEBUG = "debug"


@dataclass(slots=True)
class Bounds:
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
        }


@dataclass(slots=True)
class WindowInfo:
    window_id: str
    title: str
    platform: PlatformKind
    bounds: Bounds
    process_id: int | None = None
    process_name: str | None = None
    is_visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "title": self.title,
            "platform": self.platform.value,
            "bounds": self.bounds.to_dict(),
            "process_id": int(self.process_id) if self.process_id is not None else None,
            "process_name": self.process_name,
            "is_visible": self.is_visible,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WindowInfo":
        return cls(
            window_id=payload["window_id"],
            title=payload["title"],
            platform=PlatformKind(payload["platform"]),
            bounds=Bounds(**payload["bounds"]),
            process_id=payload.get("process_id"),
            process_name=payload.get("process_name"),
            is_visible=payload.get("is_visible", True),
        )


@dataclass(slots=True)
class ElementInfo:
    element_id: str
    window_id: str
    platform: PlatformKind
    text: str
    bounds: Bounds
    class_name: str | None = None
    control_type: str | None = None
    automation_id: str | None = None
    source: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "window_id": self.window_id,
            "platform": self.platform.value,
            "text": self.text,
            "bounds": self.bounds.to_dict(),
            "class_name": self.class_name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "source": self.source,
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ElementInfo":
        return cls(
            element_id=payload["element_id"],
            window_id=payload["window_id"],
            platform=PlatformKind(payload["platform"]),
            text=payload["text"],
            bounds=Bounds(**payload["bounds"]),
            class_name=payload.get("class_name"),
            control_type=payload.get("control_type"),
            automation_id=payload.get("automation_id"),
            source=payload.get("source"),
            confidence=payload.get("confidence"),
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class Artifact:
    kind: ArtifactKind
    path: str
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionResult:
    ok: bool
    code: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    timing_ms: int | None = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionState:
    session_id: str
    profile: str
    operator: str
    started_at: datetime
    platform: PlatformKind
    artifacts_dir: str
    allow_sensitive_windows: bool
    allow_destructive_actions: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["started_at"] = self.started_at.isoformat()
        payload["platform"] = self.platform.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionState":
        return cls(
            session_id=payload["session_id"],
            profile=payload["profile"],
            operator=payload["operator"],
            started_at=datetime.fromisoformat(payload["started_at"]),
            platform=PlatformKind(payload["platform"]),
            artifacts_dir=payload["artifacts_dir"],
            allow_sensitive_windows=payload["allow_sensitive_windows"],
            allow_destructive_actions=payload["allow_destructive_actions"],
            metadata=payload.get("metadata", {}),
        )
