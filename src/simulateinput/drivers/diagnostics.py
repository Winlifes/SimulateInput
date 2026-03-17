from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RemediationHint:
    kind: str
    permission: str
    reason: str
    system_settings_path: list[str] = field(default_factory=list)
    shell_hint: str | None = None
    copyable_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.shell_hint is None:
            payload.pop("shell_hint", None)
        if not self.metadata:
            payload.pop("metadata", None)
        return payload


def permission_remediation(
    permission: str,
    reason: str,
    system_settings_path: list[str],
    *,
    shell_hint: str | None = None,
    copyable_steps: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return RemediationHint(
        kind="permission",
        permission=permission,
        reason=reason,
        system_settings_path=system_settings_path,
        shell_hint=shell_hint,
        copyable_steps=copyable_steps or [],
        metadata=metadata or {},
    ).to_dict()
