from types import SimpleNamespace

import pytest

BOT_ENV = SimpleNamespace(
    BOT_TOKEN="fake-discord-token",
    GITHUB_ORG="ghostty-org",
    GITHUB_REPOS={"main": "ghostty", "bot": "discord-bot", "web": "website"},
    GITHUB_TOKEN="fake-gh-token",
    BOT_ACCEPT_INVITE_URL="https://youtu.be/-8KqaxE7kD0",
    SENTRY_DSN=None,
    BOT_HELP_CHANNEL_TAG_IDS={
        "moved": "1214210403",
        "solved": "181411210403",
        "stale": "1819001104",
        "duplicate": "032015110802001904",
    },
    BOT_HELP_CHANNEL_ID="07041115",
    BOT_LOG_CHANNEL_ID="011419111406",
    BOT_MEDIA_CHANNEL_ID="1204030800",
    BOT_SHOWCASE_CHANNEL_ID="1807142202001804",
    BOT_MOD_ROLE_ID="121403",
    BOT_HELPER_ROLE_ID="070411150417",
)


@pytest.fixture
def bot_env() -> SimpleNamespace:
    return BOT_ENV


def safe_environ() -> dict[str, str]:
    base_env = BOT_ENV.__dict__
    int_keys = dict.fromkeys((k for k in base_env if k.endswith("_ID")), "0")
    kv_keys = dict.fromkeys(("GITHUB_REPOS", "BOT_HELP_CHANNEL_TAG_IDS"), "a:1")
    return dict.fromkeys(base_env, "") | kv_keys | int_keys
