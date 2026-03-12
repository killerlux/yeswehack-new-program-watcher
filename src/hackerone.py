"""HackerOne opportunity fetching and parsing helpers."""

from __future__ import annotations

import time
from typing import Any

import requests

HACKERONE_GRAPHQL_URL = "https://hackerone.com/graphql"
HACKERONE_USER_AGENT = (
    "yeswehack-new-program-watcher/1.0 "
    "(+https://github.com/killerlux/yeswehack-new-program-watcher)"
)

DISCOVERY_PROGRAMS_QUERY = """
query DiscoveryProgramsQuery(
  $query: OpportunitiesQuery!
  $filter: QueryInput!
  $from: Int
  $size: Int
  $sort: [SortInput!]
) {
  opportunities_search(
    query: $query
    filter: $filter
    from: $from
    size: $size
    sort: $sort
  ) {
    total_count
    nodes {
      ... on OpportunityDocument {
        id
        name
        handle
        launched_at
        last_updated_at
        state
        submission_state
        team_type
        offers_bounties
        minimum_bounty_table_value
        maximum_bounty_table_value
        currency
      }
    }
  }
}
""".strip()


def _build_variables(offset: int, page_size: int) -> dict[str, Any]:
    return {
        "query": {"query_string": {"query": "*"}},
        "filter": {"bool": {"must": []}},
        "from": offset,
        "size": page_size,
        "sort": [{"field": "launched_at", "direction": "DESC"}],
    }


def _request_opportunities_page(
    graphql_url: str,
    timeout: int,
    retries: int,
    offset: int,
    page_size: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    payload = {
        "query": DISCOVERY_PROGRAMS_QUERY,
        "variables": _build_variables(offset=offset, page_size=page_size),
    }
    headers = {
        "User-Agent": HACKERONE_USER_AGENT,
        "Content-Type": "application/json",
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                graphql_url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            errors = body.get("errors")
            if errors:
                first_error = errors[0] if isinstance(errors, list) else errors
                message = str(first_error.get("message", "unknown GraphQL error"))
                raise RuntimeError(message)
            return body.get("data", {})
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            wait_seconds = 2 ** (attempt - 1)
            if attempt < retries:
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"Unable to fetch HackerOne opportunities after {retries} retries"
    ) from last_error


def _format_reward_range(
    minimum: int | None,
    maximum: int | None,
    currency: str | None,
) -> str | None:
    if minimum is None and maximum is None:
        return None

    prefix = str(currency or "").strip()
    low = str(minimum) if minimum is not None else "?"
    high = str(maximum) if maximum is not None else "?"
    if prefix:
        return f"{prefix}{low} - {prefix}{high}"
    return f"{low} - {high}"


def parse_hackerone_opportunities(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse HackerOne opportunity nodes into program-like records."""
    programs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for node in nodes:
        if node.get("state") != "public_mode":
            continue
        if node.get("submission_state") != "open":
            continue
        if not node.get("offers_bounties"):
            continue

        handle = str(node.get("handle") or "").strip()
        if not handle:
            continue

        raw_id = str(node.get("id") or handle).strip()
        program_id = f"hackerone:{raw_id}"
        if program_id in seen_ids:
            continue
        seen_ids.add(program_id)

        minimum_bounty = node.get("minimum_bounty_table_value")
        maximum_bounty = node.get("maximum_bounty_table_value")
        reward_range = _format_reward_range(
            minimum=minimum_bounty if isinstance(minimum_bounty, int) else None,
            maximum=maximum_bounty if isinstance(maximum_bounty, int) else None,
            currency=str(node.get("currency") or "").strip() or None,
        )

        name = str(node.get("name") or handle).strip() or handle
        url = f"https://hackerone.com/{handle}"
        programs.append(
            {
                "id": program_id,
                "source": "hackerone",
                "name": name,
                "company": name,
                "category": str(node.get("team_type") or "Bug bounty").strip(),
                "scope_count": None,
                "reward_range": reward_range,
                "url": url,
                "last_update": node.get("last_updated_at"),
                "launched_at": node.get("launched_at"),
            }
        )

    return programs


def fetch_hackerone_programs(
    timeout: int,
    retries: int,
    page_size: int = 20,
    max_pages: int = 30,
    graphql_url: str = HACKERONE_GRAPHQL_URL,
) -> list[dict[str, Any]]:
    """Fetch public HackerOne opportunities and return bounty programs only."""
    all_nodes: list[dict[str, Any]] = []
    total_count: int | None = None

    for page_index in range(max_pages):
        offset = page_index * page_size
        data = _request_opportunities_page(
            graphql_url=graphql_url,
            timeout=timeout,
            retries=retries,
            offset=offset,
            page_size=page_size,
        )
        search = data.get("opportunities_search")
        if not isinstance(search, dict):
            raise RuntimeError("Invalid HackerOne opportunities response shape")

        page_nodes = search.get("nodes", [])
        if not isinstance(page_nodes, list):
            raise RuntimeError("Invalid HackerOne opportunities nodes payload")

        if isinstance(search.get("total_count"), int):
            total_count = int(search["total_count"])

        if not page_nodes:
            break

        all_nodes.extend(page_nodes)

        if total_count is not None and len(all_nodes) >= total_count:
            break
        if len(page_nodes) < page_size:
            break

    return parse_hackerone_opportunities(all_nodes)
