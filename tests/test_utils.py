from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import discord
import pytest

from app.utils import Account, is_dm, post_has_tag, post_is_solved


@pytest.mark.parametrize(
    ("type_", "result"), [(discord.Member, False), (discord.User, True)]
)
def test_is_dm(*, type_: type[Account], result: bool) -> None:
    assert is_dm(Mock(type_)) == result


@pytest.mark.parametrize(
    ("tag", "result"),
    [
        ("foo", True),
        ("bar", True),
        ("baz", False),
        ("lorem", True),
        ("ipsum", True),
        ("dolor", False),
        ("sit", False),
        ("not", True),
        ("mac", True),
        ("windows", False),
    ],
)
def test_post_has_tag(*, tag: str, result: bool) -> None:
    tags = [
        discord.ForumTag(name=name)
        for name in ("foo", "bar", "Lorem", "ipSUM", "NOT_ISSUE", "macos", "linux")
    ]
    assert (
        post_has_tag(cast("discord.Thread", SimpleNamespace(applied_tags=tags)), tag)
        == result
    )


@pytest.mark.parametrize(
    "names",
    [
        ["solved"],
        ["solved", "solved", "solved"],
        ["solved", "duplicate", "linux"],
        ["Moved to GitHub!", "linux"],
        ["very stale"],
        ["too stale to look at", "macos"],
    ],
)
def test_post_is_solved(names: list[str]) -> None:
    tags = [discord.ForumTag(name=name) for name in names]
    assert post_is_solved(cast("discord.Thread", SimpleNamespace(applied_tags=tags)))


@pytest.mark.parametrize(
    "names",
    [
        ["solving", "linux"],
        ["help"],
        ["other", "meta"],
        ["other", "macos"],
        ["Moved to GitLab", "windows"],
    ],
)
def test_post_is_not_solved(names: list[str]) -> None:
    tags = [discord.ForumTag(name=name) for name in names]
    assert not post_is_solved(
        cast("discord.Thread", SimpleNamespace(applied_tags=tags))
    )
