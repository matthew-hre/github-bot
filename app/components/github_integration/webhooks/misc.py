from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from app.components.github_integration.commits import CommitKey, commit_cache
from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    client,
    send_embed,
)

if TYPE_CHECKING:
    from monalisten.types import CommitCommentEvent


@client.on("commit_comment")
async def handle_commit_comment_event(event: CommitCommentEvent) -> None:
    full_sha = event.comment.commit_id
    sha = full_sha[:7]

    owner, _, repo_name = event.repository.full_name.partition("/")
    if commit_summary := await commit_cache.get(CommitKey(owner, repo_name, full_sha)):
        commit_title = commit_summary.message.splitlines()[0]
    else:
        logger.warning(f"no commit summary found for {full_sha}")
        commit_title = "(no commit message found)"

    await send_embed(
        event.sender,
        EmbedContent(
            f"commented on commit `{sha}`", event.comment.html_url, event.comment.body
        ),
        Footer("commit", f"Commit {sha}: {commit_title}"),
    )
