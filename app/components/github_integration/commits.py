import asyncio
import datetime as dt
import re
import string
from collections.abc import AsyncIterator, Iterable
from contextlib import suppress
from typing import NamedTuple

import discord as dc
from githubkit.exception import RequestFailed

from app.common.hooks import (
    ItemActions,
    MessageLinker,
    ProcessedMessage,
    create_delete_hook,
    create_edit_hook,
    remove_view_after_delay,
)
from app.components.github_integration.mentions.fmt import entity_emojis
from app.components.github_integration.mentions.resolution import (
    REPO_ALIASES,
    owner_cache,
)
from app.components.github_integration.models import GitHubUser
from app.setup import config, gh
from app.utils import dynamic_timestamp

type CommitKey = tuple[str, str, str]

COMMIT_SHA_PATTERN = re.compile(
    r"\b(?:"
        r"(?P<owner>\b[a-z0-9\-]+/)?"
        r"(?P<repo>\b[a-z0-9\-\._]+)"
    r"@)?"
    r"(?P<sha>[a-z0-9]{7,40})\b",
    re.IGNORECASE,
)  # fmt: skip


class CommitSummary(NamedTuple):
    sha: str
    author: GitHubUser | None
    committer: GitHubUser | None
    message: str
    url: str
    date: dt.datetime | None
    signed: bool


class CommitCache:
    def __init__(self) -> None:
        self._cache: dict[CommitKey, CommitSummary] = {}

    async def get(self, key: CommitKey) -> CommitSummary | None:
        # TODO(trag1c): don't do this
        key = (*key[:2], key[2][:7])  # Force short SHA
        if key not in self._cache:
            await self._fetch(key)
        return self._cache.get(key)

    async def _fetch(self, key: CommitKey) -> None:
        try:
            resp = await gh.rest.repos.async_get_commit(*key)
        except RequestFailed:
            return
        obj = resp.parsed_data
        self._cache[key] = CommitSummary(
            sha=obj.sha,
            author=GitHubUser(**a.model_dump()) if (a := obj.author) else None,
            committer=GitHubUser(**c.model_dump()) if (c := obj.committer) else None,
            message=obj.commit.message,
            url=obj.html_url,
            date=(c := obj.commit.committer) and (c.date or None),
            signed=bool((v := obj.commit.verification) and v.verified),
        )


commit_cache = CommitCache()
commit_linker = MessageLinker()


class CommitActions(ItemActions):
    linker = commit_linker
    action_singular = "mentioned this commit"
    action_plural = "mentioned these commits"


def _format_commit_mention(commit: CommitSummary) -> str:
    emoji = entity_emojis.get("commit")
    title = commit.message.splitlines()[0]
    heading = f"{emoji} **Commit [`{commit.sha[:7]}`](<{commit.url}>):** {title}"

    if commit.committer and commit.committer.name == "web-flow":
        # `web-flow` is GitHub's committer account for all web commits (like merge or
        # revert) made on GitHub.com, so let's pretend the commit author is actually
        # the committer.
        commit = commit._replace(committer=commit.author)

    subtext = "\n-# authored by "
    if (a := commit.author) and (c := commit.committer) and a.name != c.name:
        subtext += f"{commit.author.hyperlink}, committed by "

    if commit.signed:
        subtext += "🔏 "

    subtext += commit.committer.hyperlink if commit.committer else "an unknown user"

    repo_url = commit.url.rstrip(string.hexdigits).removesuffix("/commit/")
    _, owner, name = repo_url.rsplit("/", 2)
    subtext += f" in [`{owner}/{name}`](<{repo_url}>)"

    if commit.date:
        subtext += f" on {dynamic_timestamp(commit.date, 'D')}"
        subtext += f" ({dynamic_timestamp(commit.date, 'R')})"

    return heading + subtext


# TODO(trag1c): merge this w/ the other one
async def resolve_repo_signatures(
    sigs: Iterable[tuple[str, str, str]],
) -> AsyncIterator[tuple[str, str, str]]:
    for owner, repo, sha in sigs:
        match owner, repo:
            case "", "":
                # Bare SHA -> ghostty-org/ghostty
                yield config.GITHUB_ORG, config.GITHUB_REPOS["main"], sha
            case "", repo if repo in config.GITHUB_REPOS:
                # Special ghostty-org prefixes
                yield config.GITHUB_ORG, config.GITHUB_REPOS[repo], sha
            case "", repo if repo in REPO_ALIASES:
                # Aliases for special ghostty-org prefixes
                yield config.GITHUB_ORG, config.GITHUB_REPOS[REPO_ALIASES[repo]], sha
            case "", repo:
                # Only a name was provided, e.g. zig@14f1178...
                with suppress(RequestFailed, RuntimeError):
                    yield await owner_cache.get(repo), repo, sha
            case owner, "":
                # Invalid case, e.g. trag1c/@a765df8...
                continue
            case owner, repo:
                # Any public repo, e.g. trag1c/zig-codeblocks@fa8d6bc
                yield owner.rstrip("/"), repo, sha


async def commit_links(message: dc.Message) -> ProcessedMessage:
    shas = dict.fromkeys(COMMIT_SHA_PATTERN.findall(message.content))
    shas = [r async for r in resolve_repo_signatures(shas)]
    commit_summaries = await asyncio.gather(*(commit_cache.get(c) for c in shas))
    valid_shas = list(filter(None, commit_summaries))
    content = "\n\n".join(map(_format_commit_mention, valid_shas))
    return ProcessedMessage(item_count=len(valid_shas), content=content)


async def reply_with_commit_details(message: dc.Message) -> None:
    output = await commit_links(message)
    if output.item_count == 0:
        return
    reply = await message.reply(
        output.content,
        mention_author=False,
        suppress_embeds=True,
        allowed_mentions=dc.AllowedMentions.none(),
        view=CommitActions(message, output.item_count),
    )
    commit_linker.link(message, reply)
    await remove_view_after_delay(reply)


commit_mention_delete_hook = create_delete_hook(linker=commit_linker)

commit_mention_edit_hook = create_edit_hook(
    linker=commit_linker,
    message_processor=commit_links,
    interactor=reply_with_commit_details,
    view_type=CommitActions,
)
