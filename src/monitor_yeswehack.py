"""Monitor public bug bounty sources and alert on first-seen IDs."""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from src.hackerone import fetch_hackerone_programs
from src.notifiers import notify_new_programs
from src.parser import parse_programs
from src.state import detect_new_programs, load_state, update_state, write_state

YESWEHACK_SOURCE_URL = "https://yeswehack.com/programs"
HACKERONE_GRAPHQL_URL = "https://hackerone.com/graphql"
DEFAULT_SOURCES = "yeswehack,hackerone"
DEFAULT_STATE_PATH = Path(".data/seen_programs.json")
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
DEFAULT_HACKERONE_PAGE_SIZE = 20
DEFAULT_HACKERONE_MAX_PAGES = 30
USER_AGENT = "yeswehack-new-program-watcher/1.0 (+https://github.com/killerlux/yeswehack-new-program-watcher)"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def fetch_programs_page(url: str, timeout: int, retries: int) -> str:
    """Fetch source HTML with retries and exponential backoff."""
    last_error: Exception | None = None
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            wait_seconds = 2 ** (attempt - 1)
            logging.warning(
                "Fetch attempt %s/%s failed: %s. Retrying in %ss.",
                attempt,
                retries,
                exc,
                wait_seconds,
            )
            if attempt < retries:
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"Unable to fetch source after {retries} retries"
    ) from last_error


def parse_sources(raw: str) -> set[str]:
    """Parse and validate comma-separated source list."""
    values = {item.strip().lower() for item in raw.split(",") if item.strip()}
    allowed = {"yeswehack", "hackerone"}
    invalid = sorted(values - allowed)
    if invalid:
        raise ValueError(f"Invalid source(s): {', '.join(invalid)}")
    if not values:
        raise ValueError("At least one source must be selected")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect new public bug bounty programs by first-seen IDs.",
    )
    parser.add_argument(
        "--sources",
        default=DEFAULT_SOURCES,
        help="Comma-separated sources to monitor (yeswehack,hackerone).",
    )
    parser.add_argument(
        "--yeswehack-url",
        default=YESWEHACK_SOURCE_URL,
        help="YesWeHack public listing URL.",
    )
    parser.add_argument(
        "--hackerone-graphql-url",
        default=HACKERONE_GRAPHQL_URL,
        help="HackerOne GraphQL endpoint.",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_PATH),
        help="Path to state JSON file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="HTTP retry count.",
    )
    parser.add_argument(
        "--hackerone-page-size",
        type=int,
        default=DEFAULT_HACKERONE_PAGE_SIZE,
        help="Number of opportunities fetched per HackerOne request.",
    )
    parser.add_argument(
        "--hackerone-max-pages",
        type=int,
        default=DEFAULT_HACKERONE_MAX_PAGES,
        help="Maximum number of HackerOne pages to fetch per run.",
    )
    return parser.parse_args()


def _has_seen_source(state: dict[str, Any], source: str) -> bool:
    seen_ids = [str(value) for value in state.get("seen_ids", [])]
    if source == "yeswehack":
        has_legacy_yeswehack_ids = any(":" not in value for value in seen_ids)
        if has_legacy_yeswehack_ids:
            return True
    return any(value.startswith(f"{source}:") for value in seen_ids)


def collect_programs(
    args: argparse.Namespace, logger: logging.Logger
) -> list[dict[str, Any]]:
    """Fetch and parse programs from the selected sources."""
    sources = parse_sources(args.sources)
    all_programs: list[dict[str, Any]] = []

    if "yeswehack" in sources:
        logger.info("Fetching YesWeHack list from %s", args.yeswehack_url)
        html = fetch_programs_page(
            url=args.yeswehack_url,
            timeout=args.timeout,
            retries=args.retries,
        )
        yeswehack_programs = parse_programs(html)
        for program in yeswehack_programs:
            program.setdefault("source", "yeswehack")
        logger.info("Parsed %s YesWeHack program cards", len(yeswehack_programs))
        all_programs.extend(yeswehack_programs)

    if "hackerone" in sources:
        logger.info(
            "Fetching HackerOne opportunities from %s",
            args.hackerone_graphql_url,
        )
        hackerone_programs = fetch_hackerone_programs(
            timeout=args.timeout,
            retries=args.retries,
            page_size=args.hackerone_page_size,
            max_pages=args.hackerone_max_pages,
            graphql_url=args.hackerone_graphql_url,
        )
        logger.info("Parsed %s HackerOne bounty opportunities", len(hackerone_programs))
        all_programs.extend(hackerone_programs)

    deduplicated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for program in all_programs:
        program_id = str(program.get("id", "")).strip()
        if not program_id:
            continue
        if program_id in seen_ids:
            continue
        seen_ids.add(program_id)
        deduplicated.append(program)

    return deduplicated


def bootstrap_new_sources_without_alerts(
    programs: list[dict[str, Any]],
    state: dict[str, Any],
    detected_at: str,
    logger: logging.Logger,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Seed newly enabled sources once, without emitting notifications."""
    if not state.get("seen_ids"):
        return programs, state, []

    source_names = sorted({str(program.get("source") or "") for program in programs})
    sources_to_seed = [
        source
        for source in source_names
        if source and not _has_seen_source(state, source)
    ]
    if not sources_to_seed:
        return programs, state, []

    bootstrap_programs = [
        program
        for program in programs
        if str(program.get("source") or "") in sources_to_seed
    ]
    bootstrap_ids = {str(program.get("id", "")) for program in bootstrap_programs}
    remaining_programs = [
        program
        for program in programs
        if str(program.get("id", "")) not in bootstrap_ids
    ]

    updated_state = update_state(state, bootstrap_programs, detected_at=detected_at)
    logger.info(
        "Seeded %s newly-enabled source(s) without alerts: %s",
        len(sources_to_seed),
        ", ".join(sources_to_seed),
    )
    return remaining_programs, updated_state, sources_to_seed


def main() -> int:
    configure_logging()
    args = parse_args()
    logger = logging.getLogger(__name__)
    detected_at = utc_now_iso()

    selected_sources = parse_sources(args.sources)
    logger.info("Selected sources: %s", ", ".join(sorted(selected_sources)))

    state_path = Path(args.state_file)
    logger.info("Loading state from %s", state_path)
    state = load_state(state_path)

    programs = collect_programs(args=args, logger=logger)
    logger.info("Collected %s total program(s) after deduplication", len(programs))

    if not programs:
        raise RuntimeError("Parsed zero programs from all selected sources")

    if not state.get("seen_ids"):
        logger.info(
            "Bootstrap run detected (empty state). Seeding %s programs without alerts.",
            len(programs),
        )
        bootstrapped_state = update_state(state, programs, detected_at=detected_at)
        write_state(state_path, bootstrapped_state)
        logger.info("Bootstrap state written to %s", state_path)
        return 0

    programs, state, seeded_sources = bootstrap_new_sources_without_alerts(
        programs=programs,
        state=state,
        detected_at=detected_at,
        logger=logger,
    )
    if seeded_sources:
        write_state(state_path, state)
        logger.info("State written to %s after source seeding", state_path)

    new_programs = detect_new_programs(programs, state)
    logger.info("Detected %s new program(s)", len(new_programs))

    if new_programs:
        env = {key: value for key, value in os.environ.items()}
        notify_new_programs(new_programs, detected_at=detected_at, env=env)

    updated_state = update_state(state, new_programs, detected_at=detected_at)
    write_state(state_path, updated_state)
    logger.info("State written to %s", state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
