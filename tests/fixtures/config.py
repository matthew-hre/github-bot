from types import SimpleNamespace

import pytest


@pytest.fixture
def bot_config() -> SimpleNamespace:
    return SimpleNamespace(
        BOT_TOKEN="fake-discord-token",
        GITHUB_ORG="ghostty-org",
        GITHUB_REPOS={"main": "ghostty", "bot": "discord-bot", "web": "website"},
        GITHUB_TOKEN="fake-gh-token",
        ACCEPT_INVITE_URL="https://discord.com/",
        SENTRY_DSN=None,
        HELP_CHANNEL_TAG_IDS={
            "moved": "1214210403",
            "solved": "181411210403",
            "stale": "1819001104",
            "duplicate": "032015110802001904",
        },
        HELP_CHANNEL_ID="07041115",
        LOG_CHANNEL_ID="011419111406",
        MEDIA_CHANNEL_ID="1204030800",
        SHOWCASE_CHANNEL_ID="1807142202001804",
        MOD_ROLE_ID="121403",
        HELPER_ROLE_ID="070411150417",
    )
