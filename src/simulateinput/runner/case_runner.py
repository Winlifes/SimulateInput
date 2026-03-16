from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simulateinput.core.engine import AutomationEngine
from simulateinput.core.errors import CaseValidationError


@dataclass(slots=True)
class CaseDefinition:
    name: str
    profile: str
    steps: list[dict[str, Any]]


def load_case(path: str | Path) -> CaseDefinition:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise CaseValidationError(
            "PyYAML is required to load YAML case files. Install dependencies before using 'case validate'."
        ) from exc

    case_path = Path(path)
    payload = yaml.safe_load(case_path.read_text(encoding="utf-8")) or {}
    name = payload.get("name")
    steps = payload.get("steps")
    if not isinstance(name, str) or not name.strip():
        raise CaseValidationError("case file must include a non-empty 'name'")
    if not isinstance(steps, list):
        raise CaseValidationError("case file must include a 'steps' list")
    profile = payload.get("profile", "lab_default")
    return CaseDefinition(name=name, profile=profile, steps=steps)


def run_case(
    path: str | Path,
    engine: AutomationEngine,
    operator: str = "case-runner",
) -> dict[str, Any]:
    case_def = load_case(path)
    session = engine.sessions.start(profile_name=case_def.profile, operator=operator)
    results: list[dict[str, Any]] = []

    for index, step in enumerate(case_def.steps, start=1):
        if not isinstance(step, dict):
            raise CaseValidationError(f"step {index} must be an object")
        action = step.get("action")
        if not isinstance(action, str) or not action.strip():
            raise CaseValidationError(f"step {index} must include a non-empty 'action'")
        action_name = action.strip()
        result = _run_step(engine, session.session_id, action_name, step)
        results.append({"index": index, "action": action_name, "result": result})

    return {
        "name": case_def.name,
        "profile": case_def.profile,
        "session": session.to_dict(),
        "steps": results,
    }


def _run_step(engine: AutomationEngine, session_id: str, action: str, step: dict[str, Any]) -> dict[str, Any]:
    if action == "attach_window":
        title = step.get("title")
        window_id = step.get("window_id")
        window = engine.attach_window(session_id, title=title, window_id=window_id)
        return {"ok": True, "window": window.to_dict()}
    if action == "locate_text":
        matches = engine.find_text(
            session_id,
            text=_require_str(step, "text"),
            window_id=_optional_str(step, "window_id"),
            exact=bool(step.get("exact", False)),
        )
        return {"ok": True, "matches": [match.to_dict() for match in matches]}
    if action == "locate_uia":
        matches = engine.find_uia(
            session_id,
            window_id=_optional_str(step, "window_id"),
            name=_optional_str(step, "name"),
            control_type=_optional_str(step, "control_type"),
            automation_id=_optional_str(step, "automation_id"),
            exact=bool(step.get("exact", False)),
            max_results=int(step.get("max_results", 20)),
        )
        return {"ok": True, "matches": [match.to_dict() for match in matches]}
    if action == "locate_ocr":
        matches = engine.find_ocr_text(
            session_id,
            text=_require_str(step, "text"),
            window_id=_optional_str(step, "window_id"),
            exact=bool(step.get("exact", False)),
            confidence_threshold=float(step.get("confidence_threshold", 0.0)),
        )
        return {"ok": True, "matches": [match.to_dict() for match in matches]}
    if action == "locate_image":
        matches = engine.find_image(
            session_id,
            image_path=_require_str(step, "image_path"),
            window_id=_optional_str(step, "window_id"),
            threshold=float(step.get("threshold", 0.9)),
            max_results=int(step.get("max_results", 5)),
        )
        return {"ok": True, "matches": [match.to_dict() for match in matches]}
    if action == "click_text":
        return engine.execute_click_text(
            session_id,
            text=_require_str(step, "text"),
            window_id=_optional_str(step, "window_id"),
            exact=bool(step.get("exact", False)),
        ).to_dict()
    if action == "click_uia":
        return engine.execute_click_uia(
            session_id,
            window_id=_optional_str(step, "window_id"),
            name=_optional_str(step, "name"),
            control_type=_optional_str(step, "control_type"),
            automation_id=_optional_str(step, "automation_id"),
            exact=bool(step.get("exact", False)),
        ).to_dict()
    if action == "click_ocr":
        return engine.execute_click_ocr(
            session_id,
            text=_require_str(step, "text"),
            window_id=_optional_str(step, "window_id"),
            exact=bool(step.get("exact", False)),
            confidence_threshold=float(step.get("confidence_threshold", 0.0)),
        ).to_dict()
    if action == "click_image":
        return engine.execute_click_image(
            session_id,
            image_path=_require_str(step, "image_path"),
            window_id=_optional_str(step, "window_id"),
            threshold=float(step.get("threshold", 0.9)),
        ).to_dict()
    if action == "click":
        return engine.execute_click(
            session_id,
            x=int(step["x"]),
            y=int(step["y"]),
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    if action == "type_text":
        return engine.execute_type_text(
            session_id,
            text=_require_str(step, "text"),
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    if action == "press_key":
        return engine.execute_press_key(
            session_id,
            key=_require_str(step, "key"),
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    if action == "hotkey":
        keys = step.get("keys")
        if not isinstance(keys, list) or not keys:
            raise CaseValidationError("hotkey step requires a non-empty 'keys' list")
        return engine.execute_hotkey(
            session_id,
            keys=[str(key) for key in keys],
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    if action == "clear_text":
        return engine.execute_clear_text(
            session_id,
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    if action == "screenshot":
        return engine.execute_screenshot(
            session_id,
            output=_require_str(step, "output"),
            window_id=_optional_str(step, "window_id"),
        ).to_dict()
    raise CaseValidationError(f"unsupported case action: {action}")


def _require_str(step: dict[str, Any], key: str) -> str:
    value = step.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CaseValidationError(f"step requires a non-empty '{key}'")
    return value


def _optional_str(step: dict[str, Any], key: str) -> str | None:
    value = step.get(key)
    if value is None:
        return None
    return str(value)
