"""Notification helpers for chat/email channels."""

from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def channels_from_env(env: dict[str, str]) -> list[str]:
    """Return configured notification channels based on environment values."""
    channels: list[str] = []

    if env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"):
        channels.append("telegram")
    if env.get("DISCORD_WEBHOOK_URL"):
        channels.append("discord")

    return channels


def build_notification_text(program: dict[str, Any], detected_at: str) -> str:
    """Build notification text payload for a single new program."""
    lines = [
        "New YesWeHack public program detected",
        f"Program: {program.get('name', 'Unknown')}",
        f"Company: {program.get('company') or 'Unknown'}",
        f"Category: {program.get('category') or 'Unknown'}",
        f"Rewards: {program.get('reward_range') or 'N/A'}",
        f"Scope count: {program.get('scope_count') if program.get('scope_count') is not None else 'N/A'}",
        f"URL: {program.get('url')}",
        f"Detected at (UTC): {detected_at}",
    ]
    return "\n".join(lines)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send one Telegram message using Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()


def send_discord_message(webhook_url: str, text: str) -> None:
    """Send one Discord webhook message."""
    response = requests.post(
        webhook_url,
        json={"content": text},
        timeout=20,
    )
    response.raise_for_status()


def notify_new_programs(
    programs: list[dict[str, Any]], detected_at: str, env: dict[str, str]
) -> None:
    """Notify configured channels for each new program."""
    channels = channels_from_env(env)
    if not channels:
        LOGGER.warning("No notification channels configured; state will still update.")
        return

    for program in programs:
        text = build_notification_text(program, detected_at=detected_at)

        if "telegram" in channels:
            send_telegram_message(
                bot_token=env["TELEGRAM_BOT_TOKEN"],
                chat_id=env["TELEGRAM_CHAT_ID"],
                text=text,
            )

        if "discord" in channels:
            send_discord_message(
                webhook_url=env["DISCORD_WEBHOOK_URL"],
                text=text,
            )
