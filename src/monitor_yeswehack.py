"""Monitor YesWeHack public programs and alert on first-seen IDs."""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.notifiers import notify_new_programs
from src.parser import parse_programs
from src.state import detect_new_programs, load_state, update_state, write_state

DEFAULT_SOURCE_URL = "https://yeswehack.com/programs"
DEFAULT_STATE_PATH = Path(".data/seen_programs.json")
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect new public YesWeHack programs by first-seen IDs.",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Public listing URL to monitor.",
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
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    logger = logging.getLogger(__name__)
    detected_at = utc_now_iso()

    state_path = Path(args.state_file)
    logger.info("Loading state from %s", state_path)
    state = load_state(state_path)

    logger.info("Fetching program list from %s", args.source_url)
    html = fetch_programs_page(
        args.source_url, timeout=args.timeout, retries=args.retries
    )

    programs = parse_programs(html)
    logger.info("Parsed %s program cards", len(programs))

    if not programs:
        raise RuntimeError("Parsed zero programs; refusing to overwrite state")

    if not state.get("seen_ids"):
        logger.info(
            "Bootstrap run detected (empty state). Seeding %s programs without alerts.",
            len(programs),
        )
        bootstrapped_state = update_state(state, programs, detected_at=detected_at)
        write_state(state_path, bootstrapped_state)
        logger.info("Bootstrap state written to %s", state_path)
        return 0

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
