import logging

from src.monitor_yeswehack import (
    bootstrap_new_sources_without_alerts,
    parse_sources,
)


def test_parse_sources_accepts_known_values() -> None:
    sources = parse_sources("yeswehack,hackerone")

    assert sources == {"yeswehack", "hackerone"}


def test_bootstrap_new_sources_seeds_hackerone_once() -> None:
    state = {
        "seen_ids": ["legacy-yeswehack-id"],
        "programs": {"legacy-yeswehack-id": {"name": "Old YWH", "url": "x"}},
    }
    programs = [
        {"id": "legacy-yeswehack-id", "source": "yeswehack", "name": "Old YWH"},
        {
            "id": "hackerone:123",
            "source": "hackerone",
            "name": "H1 Program",
            "url": "https://hackerone.com/h1",
        },
    ]

    remaining, updated_state, seeded_sources = bootstrap_new_sources_without_alerts(
        programs=programs,
        state=state,
        detected_at="2026-03-11T12:00:00Z",
        logger=logging.getLogger("test"),
    )

    assert seeded_sources == ["hackerone"]
    assert [item["id"] for item in remaining] == ["legacy-yeswehack-id"]
    assert "hackerone:123" in updated_state["seen_ids"]
