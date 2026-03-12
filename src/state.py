"""State persistence helpers for first-seen detection."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_STATE: dict[str, Any] = {
    "seen_ids": [],
    "programs": {},
}


def load_state(path: Path) -> dict[str, Any]:
    """Load state from disk, returning defaults when missing/invalid."""
    if not path.exists():
        return deepcopy(DEFAULT_STATE)

    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)

    if not isinstance(parsed, dict):
        return deepcopy(DEFAULT_STATE)

    seen_ids = parsed.get("seen_ids", [])
    programs = parsed.get("programs", {})
    if not isinstance(seen_ids, list):
        seen_ids = []
    if not isinstance(programs, dict):
        programs = {}

    return {"seen_ids": seen_ids, "programs": programs}


def write_state(path: Path, state: dict[str, Any]) -> None:
    """Write state to disk with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def detect_new_programs(
    programs: list[dict[str, Any]], state: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return programs with IDs not currently seen in state."""
    seen_ids = set(str(item) for item in state.get("seen_ids", []))

    new_programs: list[dict[str, Any]] = []
    queued_ids: set[str] = set()
    for program in programs:
        program_id = str(program.get("id", "")).strip()
        if not program_id:
            continue
        if program_id in seen_ids or program_id in queued_ids:
            continue
        queued_ids.add(program_id)
        new_programs.append(program)

    return new_programs


def update_state(
    state: dict[str, Any], new_programs: list[dict[str, Any]], detected_at: str
) -> dict[str, Any]:
    """Update state while preserving all previously seen IDs."""
    updated = deepcopy(state)
    seen_ids = [str(item) for item in updated.get("seen_ids", [])]
    seen_set = set(seen_ids)

    programs_index = updated.get("programs", {})
    if not isinstance(programs_index, dict):
        programs_index = {}

    for program in new_programs:
        program_id = str(program.get("id", "")).strip()
        if not program_id:
            continue
        if program_id not in seen_set:
            seen_ids.append(program_id)
            seen_set.add(program_id)

        programs_index[program_id] = {
            "name": program.get("name"),
            "url": program.get("url"),
            "source": program.get("source"),
            "first_seen_at": detected_at,
        }

    updated["seen_ids"] = seen_ids
    updated["programs"] = programs_index
    return updated
