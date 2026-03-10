"""Parsing helpers for YesWeHack public program cards."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

BASE_URL = "https://yeswehack.com"
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def normalize_whitespace(value: str) -> str:
    """Normalize all whitespace to single spaces."""
    return " ".join(value.split())


def extract_stable_program_id(program: dict[str, Any]) -> str:
    """Extract a stable identity for a program card.

    Priority order:
    1) UUID found in raw card HTML
    2) Canonical URL
    3) Deterministic fallback hash
    """

    raw_html = str(program.get("raw_html", ""))
    uuid_match = UUID_RE.search(raw_html)
    if uuid_match:
        return uuid_match.group(0).lower()

    url = normalize_whitespace(str(program.get("url", "")))
    if url:
        return f"url:{url.lower()}"

    fingerprint_source = "|".join(
        [
            normalize_whitespace(str(program.get("name", ""))).lower(),
            normalize_whitespace(str(program.get("company", ""))).lower(),
        ]
    )
    digest = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    return f"hash:{digest}"


def _extract_scope_count(lines: list[str]) -> int | None:
    for line in lines:
        match = re.search(r"(\d+)\s+scopes?", line, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_reward_range(lines: list[str]) -> str | None:
    if "Rewards" not in lines:
        return None

    start_idx = lines.index("Rewards") + 1
    stop_labels = {"Last update on", "View Program", "Reports", "1st response"}
    parts: list[str] = []

    for item in lines[start_idx:]:
        if item in stop_labels:
            break
        parts.append(item)

    if not parts:
        return None

    reward = normalize_whitespace(" ".join(parts))
    return reward or None


def _extract_last_update(lines: list[str]) -> str | None:
    if "Last update on" not in lines:
        return None
    idx = lines.index("Last update on")
    if idx + 1 < len(lines):
        return lines[idx + 1]
    return None


def _extract_program_link(card: Any) -> tuple[str | None, str | None]:
    for link in card.select("a[href]"):
        href = normalize_whitespace(link.get("href", ""))
        if not href or "/programs/" not in href:
            continue
        url = urljoin(BASE_URL, href)
        name = normalize_whitespace(link.get_text(" ", strip=True))
        return name or None, url
    return None, None


def _build_card_lines(card: Any) -> list[str]:
    lines: list[str] = []
    for chunk in card.stripped_strings:
        normalized = normalize_whitespace(str(chunk))
        if normalized:
            lines.append(normalized)
    return lines


def parse_programs(html: str) -> list[dict[str, Any]]:
    """Parse public program cards from YesWeHack listing HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("section.default-background ywh-card")

    programs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for card in cards:
        raw_html = str(card)
        lines = _build_card_lines(card)
        name, url = _extract_program_link(card)

        if not name:
            name = lines[0] if lines else "Unknown Program"
        if not url:
            continue

        company = lines[1] if len(lines) > 1 else None
        category = lines[2] if len(lines) > 2 else None
        scope_count = _extract_scope_count(lines)
        reward_range = _extract_reward_range(lines)
        last_update = _extract_last_update(lines)

        program = {
            "raw_html": raw_html,
            "name": name,
            "company": company,
            "category": category,
            "scope_count": scope_count,
            "reward_range": reward_range,
            "url": url,
            "last_update": last_update,
        }
        stable_id = extract_stable_program_id(program)
        program["id"] = stable_id

        if stable_id in seen_ids:
            continue
        seen_ids.add(stable_id)
        programs.append(program)

    return programs
