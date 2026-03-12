from src.hackerone import parse_hackerone_opportunities


def test_parse_hackerone_opportunities_filters_to_public_open_bounty() -> None:
    nodes = [
        {
            "id": "101",
            "name": "Alpha Program",
            "handle": "alpha-program",
            "state": "public_mode",
            "submission_state": "open",
            "offers_bounties": True,
            "team_type": "Engagements::BugBountyProgram",
            "minimum_bounty_table_value": 50,
            "maximum_bounty_table_value": 5000,
            "currency": "USD",
            "launched_at": "2026-03-11T09:00:00Z",
            "last_updated_at": "2026-03-11T10:00:00Z",
        },
        {
            "id": "102",
            "name": "No Bounty Program",
            "handle": "no-bounty",
            "state": "public_mode",
            "submission_state": "open",
            "offers_bounties": False,
        },
        {
            "id": "103",
            "name": "Paused Program",
            "handle": "paused-program",
            "state": "public_mode",
            "submission_state": "paused",
            "offers_bounties": True,
        },
    ]

    programs = parse_hackerone_opportunities(nodes)

    assert len(programs) == 1
    first = programs[0]
    assert first["id"] == "hackerone:101"
    assert first["source"] == "hackerone"
    assert first["url"] == "https://hackerone.com/alpha-program"
    assert first["reward_range"] == "USD50 - USD5000"


def test_parse_hackerone_opportunities_deduplicates_by_program_id() -> None:
    nodes = [
        {
            "id": "101",
            "name": "Alpha Program",
            "handle": "alpha-program",
            "state": "public_mode",
            "submission_state": "open",
            "offers_bounties": True,
        },
        {
            "id": "101",
            "name": "Alpha Program Duplicate",
            "handle": "alpha-program",
            "state": "public_mode",
            "submission_state": "open",
            "offers_bounties": True,
        },
    ]

    programs = parse_hackerone_opportunities(nodes)

    assert len(programs) == 1


def test_parse_hackerone_opportunities_handles_missing_bounty_values() -> None:
    nodes = [
        {
            "id": "201",
            "name": "Unknown Reward Program",
            "handle": "unknown-reward",
            "state": "public_mode",
            "submission_state": "open",
            "offers_bounties": True,
            "minimum_bounty_table_value": None,
            "maximum_bounty_table_value": None,
            "currency": None,
        }
    ]

    programs = parse_hackerone_opportunities(nodes)

    assert len(programs) == 1
    assert programs[0]["reward_range"] is None
