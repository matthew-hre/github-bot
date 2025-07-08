import datetime as dt
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import discord
import pytest

from app.utils import (
    Account,
    aenumerate,
    dynamic_timestamp,
    is_attachment_only,
    is_dm,
    post_has_tag,
    post_is_solved,
    truncate,
)


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


@pytest.mark.parametrize(
    "items",
    [
        [1, 2, 3, 4, 5],
        ["spam", "eggs", "bacon", "ham"],
        [False, True, True],
        [{"a": 12}, {"b": 14, "c": 23}, {"d": 183, "e": 21}],
        [..., ..., ...],
        [None, None],
        [[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6], [5, 6, 7]],
        [(1, 2, 3), (2, 3, 4), (3, 4, 5), (4, 5, 6), (5, 6, 7)],
    ],
)
@pytest.mark.parametrize("start", [0, 1, 2, 3, 4, 5, -1, -2, -3, -4, -5, 102, -99, 41])
@pytest.mark.asyncio
async def test_aenumerate[T](items: list[T], start: int) -> None:
    async def async_iterator() -> AsyncIterator[T]:
        for item in items:
            yield item

    assert [x async for x in aenumerate(async_iterator(), start)] == list(
        enumerate(items, start)
    )


@pytest.mark.parametrize(
    ("attachments", "content", "preprocessed_content", "embeds", "result"),
    [
        ([], "", None, [], False),
        ([1], "", None, [], True),
        ([1, 2, 3], "", None, [], True),
        ([1, 2, 3], "foo", "", [], True),  # The pre-processing removes the content.
        ([1, 2, 3], "", "foo", [], False),
        ([], "", "foo", [], False),
        ([1, 2, 3], "", "", [1, 2], False),
        ([1, 2, 3], "", "foo", [1, 2], False),
        ([1, 2, 3], "foo", "bar", [], False),
        ([1, 2, 3], "foo", "bar", [1, 2], False),
    ],
)
def test_is_attachment_only(
    *,
    attachments: list[int],
    content: str,
    preprocessed_content: str | None,
    embeds: list[int],
    result: bool,
) -> None:
    # NOTE: we don't actually care about having real Discord objects here, we
    # only care about whether they are truthy, so ints are used everywhere.
    fake_message = SimpleNamespace(
        attachments=attachments,
        components=[],
        content=content,
        preprocessed_content=preprocessed_content,
        embeds=embeds,
        poll=None,
        stickers=[],
    )
    assert (
        is_attachment_only(
            cast("discord.Message", fake_message),
            preprocessed_content=preprocessed_content,
        )
        == result
    )


@pytest.mark.parametrize(
    ("s", "length", "suffix", "result"),
    [
        ("aaaaaaaaaaaaaaa", 10, "", "aaaaaaaaaa"),
        ("the quick brown fox", 4, "!", "the!"),
        ("aaaaaaaaaaaaaaa", 10, "…", "aaaaaaaaa…"),
        ("", 10, "…", ""),
        ("aaaaaaaa", 10, "bbbbb", "aaaaaaaa"),
        ("aaaaaaaaaaaaaaa", 10, "...", "aaaaaaa..."),
    ],
)
def test_truncate(s: str, length: int, suffix: str, result: str) -> None:
    assert truncate(s, length, suffix=suffix) == result


@pytest.mark.parametrize(
    ("dt", "fmt", "result"),
    [
        (dt.datetime(2012, 4, 12, 15, 10, 14, tzinfo=dt.UTC), None, "<t:1334243414>"),
        (dt.datetime(2018, 1, 20, 3, 11, 33, tzinfo=dt.UTC), "R", "<t:1516417893:R>"),
        (dt.datetime(1, 1, 1, 1, 1, 1, tzinfo=dt.UTC), "a", "<t:-62135593139:a>"),
        (
            dt.datetime(9999, 12, 31, 23, 59, 59, tzinfo=dt.UTC),
            "Q",
            "<t:253402300799:Q>",
        ),
    ],
)
def test_dynamic_timestamp(dt: dt.datetime, fmt: str | None, result: str) -> None:
    assert dynamic_timestamp(dt, fmt) == result
