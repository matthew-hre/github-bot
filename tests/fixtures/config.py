from types import SimpleNamespace

import pytest

BOT_ENV = {
    "BOT_TOKEN": "fake-discord-token",
    "GITHUB_ORG": "ghostty-org",
    "GITHUB_REPOS": {"main": "ghostty", "bot": "discord-bot", "web": "website"},
    "GITHUB_TOKEN": "fake-gh-token",
    "GITHUB_WEBHOOK_URL": "https://smee.io/aBCDef1gHijKLM2N",
    "GITHUB_WEBHOOK_SECRET": "foobar",
    "BOT_ACCEPT_INVITE_URL": "https://youtu.be/-8KqaxE7kD0",
    "SENTRY_DSN": None,
    "BOT_HELP_CHANNEL_TAG_IDS": {
        "moved": "1214210403",
        "solved": "181411210403",
        "stale": "1819001104",
        "duplicate": "032015110802001904",
    },
    "BOT_HELP_CHANNEL_ID": "07041115",
    "BOT_LOG_CHANNEL_ID": "011419111406",
    "BOT_MEDIA_CHANNEL_ID": "1204030800",
    "BOT_SHOWCASE_CHANNEL_ID": "1807142202001804",
    "BOT_WEBHOOK_CHANNEL_ID": "1246449239523604510",
    "BOT_MOD_ROLE_ID": "121403",
    "BOT_HELPER_ROLE_ID": "070411150417",
}


@pytest.fixture
def bot_env() -> SimpleNamespace:
    return SimpleNamespace(
        # BOT_TOKEN should keep its prefix to match app/config.py.
        (k.removeprefix("BOT_") if k != "BOT_TOKEN" else k, v)
        for k, v in BOT_ENV.items()
    )


def safe_environ() -> dict[str, str]:
    int_keys = dict.fromkeys((k for k in BOT_ENV if k.endswith("_ID")), "0")
    kv_keys = dict.fromkeys(("GITHUB_REPOS", "BOT_HELP_CHANNEL_TAG_IDS"), "a:1")
    return dict.fromkeys(BOT_ENV, "") | kv_keys | int_keys
