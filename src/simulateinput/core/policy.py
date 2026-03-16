from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    allow_sensitive_windows: bool
    allow_system_settings: bool
    allow_security_prompts: bool
    allow_credential_fields: bool
    allow_destructive_actions: bool
    require_audit_log: bool
    require_video_recording: bool
    require_pre_action_screenshot: bool
    default_retry: int


STANDARD = ExecutionProfile(
    name="standard",
    allow_sensitive_windows=False,
    allow_system_settings=False,
    allow_security_prompts=False,
    allow_credential_fields=False,
    allow_destructive_actions=False,
    require_audit_log=True,
    require_video_recording=False,
    require_pre_action_screenshot=False,
    default_retry=1,
)

LAB_DEFAULT = ExecutionProfile(
    name="lab_default",
    allow_sensitive_windows=True,
    allow_system_settings=True,
    allow_security_prompts=False,
    allow_credential_fields=False,
    allow_destructive_actions=True,
    require_audit_log=True,
    require_video_recording=True,
    require_pre_action_screenshot=True,
    default_retry=2,
)

PRIVILEGED_LAB = ExecutionProfile(
    name="privileged_lab",
    allow_sensitive_windows=True,
    allow_system_settings=True,
    allow_security_prompts=True,
    allow_credential_fields=True,
    allow_destructive_actions=True,
    require_audit_log=True,
    require_video_recording=True,
    require_pre_action_screenshot=True,
    default_retry=2,
)

BUILTIN_PROFILES = {
    STANDARD.name: STANDARD,
    LAB_DEFAULT.name: LAB_DEFAULT,
    PRIVILEGED_LAB.name: PRIVILEGED_LAB,
}


def load_profile(name: str) -> ExecutionProfile:
    try:
        return BUILTIN_PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(BUILTIN_PROFILES))
        raise ValueError(f"unknown profile '{name}', expected one of: {available}") from exc
