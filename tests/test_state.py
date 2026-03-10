from pathlib import Path

from src.state import detect_new_programs, load_state, update_state, write_state


def test_detect_new_programs_distinguishes_seen_and_new() -> None:
    state = {
        "seen_ids": ["existing-id"],
        "programs": {
            "existing-id": {
                "name": "Existing Program",
                "url": "https://yeswehack.com/programs/existing",
                "first_seen_at": "2026-03-10T00:00:00Z",
            }
        },
    }

    programs = [
        {
            "id": "existing-id",
            "name": "Existing Program",
            "url": "https://yeswehack.com/programs/existing",
        },
        {
            "id": "new-id",
            "name": "New Program",
            "url": "https://yeswehack.com/programs/new",
        },
    ]

    new_programs = detect_new_programs(programs, state)

    assert len(new_programs) == 1
    assert new_programs[0]["id"] == "new-id"


def test_detect_new_programs_deduplicates_ids_in_same_run() -> None:
    state = {"seen_ids": [], "programs": {}}
    programs = [
        {"id": "duplicate-id", "name": "A", "url": "https://yeswehack.com/programs/a"},
        {"id": "duplicate-id", "name": "A", "url": "https://yeswehack.com/programs/a"},
    ]

    new_programs = detect_new_programs(programs, state)

    assert len(new_programs) == 1


def test_detect_new_programs_returns_empty_when_all_seen() -> None:
    state = {"seen_ids": ["known"], "programs": {}}
    programs = [
        {"id": "known", "name": "Known", "url": "https://yeswehack.com/programs/known"}
    ]

    new_programs = detect_new_programs(programs, state)

    assert new_programs == []


def test_state_round_trip(tmp_path: Path) -> None:
    state_path = tmp_path / "seen_programs.json"
    initial_state = {"seen_ids": [], "programs": {}}
    write_state(state_path, initial_state)

    loaded = load_state(state_path)
    assert loaded == initial_state


def test_update_state_keeps_existing_and_appends_new() -> None:
    state = {
        "seen_ids": ["existing-id"],
        "programs": {
            "existing-id": {
                "name": "Existing Program",
                "url": "https://yeswehack.com/programs/existing",
                "first_seen_at": "2026-03-10T00:00:00Z",
            }
        },
    }

    new_programs = [
        {
            "id": "new-id",
            "name": "New Program",
            "url": "https://yeswehack.com/programs/new",
        }
    ]

    updated = update_state(state, new_programs, detected_at="2026-03-10T12:00:00Z")

    assert updated["seen_ids"] == ["existing-id", "new-id"]
    assert updated["programs"]["existing-id"]["name"] == "Existing Program"
    assert updated["programs"]["new-id"]["first_seen_at"] == "2026-03-10T12:00:00Z"
