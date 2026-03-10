from pathlib import Path

from src.parser import extract_stable_program_id, parse_programs


def test_extract_stable_program_id_prefers_uuid() -> None:
    raw_html = (
        '<img src="https://cdn-yeswehack.com/program/thumbnail/'
        'ddad5d7e-9330-46e5-83bb-08abb8cd59dc" alt="logo">'
    )
    program = {
        "raw_html": raw_html,
        "url": "https://yeswehack.com/programs/systemd-bug-bounty-program",
        "name": "systemd Bug Bounty Program",
        "company": "Sovereign Tech Agency",
    }

    stable_id = extract_stable_program_id(program)

    assert stable_id == "ddad5d7e-9330-46e5-83bb-08abb8cd59dc"


def test_parse_programs_extracts_expected_fields() -> None:
    fixture_path = Path("tests/fixtures/programs_sample.html")
    html = fixture_path.read_text(encoding="utf-8")

    programs = parse_programs(html)

    assert len(programs) == 2

    first = programs[0]
    assert first["id"] == "ddad5d7e-9330-46e5-83bb-08abb8cd59dc"
    assert first["name"] == "systemd Bug Bounty Program"
    assert first["company"] == "Sovereign Tech Agency"
    assert first["category"] == "Government"
    assert first["reward_range"] == "EUR150 - EUR10,000"
    assert first["scope_count"] == 17
    assert first["url"] == "https://yeswehack.com/programs/systemd-bug-bounty-program"
    assert first["last_update"] == "2026-03-10"


def test_parse_programs_handles_missing_optional_fields() -> None:
    fixture_path = Path("tests/fixtures/programs_sample.html")
    html = fixture_path.read_text(encoding="utf-8")

    programs = parse_programs(html)

    second = programs[1]
    assert second["name"] == "No Reward Program"
    assert second["scope_count"] == 1
    assert second["reward_range"] is None
    assert second["last_update"] == "2026-03-09"
