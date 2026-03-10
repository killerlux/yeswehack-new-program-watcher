from src.notifiers import build_notification_text, channels_from_env


def test_build_notification_text_contains_key_fields() -> None:
    program = {
        "name": "systemd Bug Bounty Program",
        "company": "Sovereign Tech Agency",
        "category": "Government",
        "reward_range": "EUR150 - EUR10,000",
        "scope_count": 17,
        "url": "https://yeswehack.com/programs/systemd-bug-bounty-program",
    }

    message = build_notification_text(program, detected_at="2026-03-10T12:00:00Z")

    assert "New YesWeHack public program detected" in message
    assert "systemd Bug Bounty Program" in message
    assert "Sovereign Tech Agency" in message
    assert "EUR150 - EUR10,000" in message
    assert "17" in message


def test_channels_from_env_no_channels() -> None:
    env = {}

    channels = channels_from_env(env)

    assert channels == []


def test_channels_from_env_telegram_present() -> None:
    env = {
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_CHAT_ID": "123",
    }

    channels = channels_from_env(env)

    assert channels == ["telegram"]
