from __future__ import annotations

import json
import platform
from pathlib import Path
from uuid import uuid4

from simulateinput.core.errors import SessionNotFoundError
from simulateinput.core.models import PlatformKind, SessionState, utc_now
from simulateinput.core.policy import load_profile


def detect_platform() -> PlatformKind:
    system = platform.system().lower()
    if system == "windows":
        return PlatformKind.WINDOWS
    if system == "darwin":
        return PlatformKind.MACOS
    if system == "linux":
        return PlatformKind.LINUX
    return PlatformKind.UNKNOWN


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(".simctl") / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def start(self, profile_name: str, operator: str = "local-user") -> SessionState:
        profile = load_profile(profile_name)
        session_id = f"sess-{uuid4().hex[:12]}"
        artifacts_dir = Path(".simctl") / "artifacts" / session_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        session = SessionState(
            session_id=session_id,
            profile=profile.name,
            operator=operator,
            started_at=utc_now(),
            platform=detect_platform(),
            artifacts_dir=str(artifacts_dir),
            allow_sensitive_windows=profile.allow_sensitive_windows,
            allow_destructive_actions=profile.allow_destructive_actions,
            metadata={"default_retry": profile.default_retry},
        )
        self._save(session)
        return session

    def get(self, session_id: str) -> SessionState:
        path = self.root / f"{session_id}.json"
        if not path.exists():
            raise SessionNotFoundError(f"session not found: {session_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SessionState.from_dict(payload)

    def list(self) -> list[SessionState]:
        sessions: list[SessionState] = []
        for path in sorted(self.root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(SessionState.from_dict(payload))
        return sessions

    def save(self, session: SessionState) -> None:
        self._save(session)

    def _save(self, session: SessionState) -> None:
        path = self.root / f"{session.session_id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
