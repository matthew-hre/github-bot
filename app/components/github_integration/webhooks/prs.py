from __future__ import annotations

import datetime as dt
from itertools import dropwhile
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    cast,
    final,
    override,
)

from discord.ext import commands
from loguru import logger

from app.components.github_integration.models import GitHubUser
from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    SubhookStore,
    client,
    make_subhook_registrar,
    reraise_with_payload,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.versions.latest.models import (
        WebhookPullRequestClosed,
        WebhookPullRequestConvertedToDraft,
        WebhookPullRequestEdited,
        WebhookPullRequestLocked,
        WebhookPullRequestOpened,
        WebhookPullRequestReadyForReview,
        WebhookPullRequestReopened,
        WebhookPullRequestReviewCommentCreated,
        WebhookPullRequestReviewDismissed,
        WebhookPullRequestReviewRequestedOneof0,
        WebhookPullRequestReviewRequestedOneof1,
        WebhookPullRequestReviewRequestRemovedOneof0,
        WebhookPullRequestReviewRequestRemovedOneof1,
        WebhookPullRequestReviewSubmitted,
        WebhookPullRequestUnlocked,
    )
    from monalisten import Monalisten
    from monalisten.types import (
        PullRequestEvent,
        PullRequestReviewCommentEvent,
        PullRequestReviewEvent,
    )

    from app.bot import GhosttyBot
    from app.components.github_integration.emoji import EmojiName

type WebhookPullRequestReviewRequested = (
    WebhookPullRequestReviewRequestedOneof0 | WebhookPullRequestReviewRequestedOneof1
)
type WebhookPullRequestReviewRequestRemoved = (
    WebhookPullRequestReviewRequestRemovedOneof0
    | WebhookPullRequestReviewRequestRemovedOneof1
)

HUNK_CODEBLOCK_OVERHEAD = len("```diff\n\n```\n")

pr_subhooks: SubhookStore[PullRequestEvent] = {}
pr_review_subhooks: SubhookStore[PullRequestReviewEvent] = {}

register_pr_subhook = make_subhook_registrar(pr_subhooks)
register_pr_review_subhook = make_subhook_registrar(pr_review_subhooks)


class PRLike(Protocol):
    number: int
    title: str
    html_url: str
    draft: Any
    merged_at: Any
    state: Any


def pr_footer(
    pr: PRLike, *, emoji: EmojiName | None = None, from_review: bool = False
) -> Footer:
    if emoji is None:
        # pull_request_review(_comment) events have pull_request objects that don't have
        # the .merged field, so we have to fall back to checking if .merged_at is truthy
        merged = pr.merged_at is not None if from_review else cast("Any", pr).merged
        state = cast("Literal['open', 'closed']", pr.state)
        emoji = "pull_" + ("draft" if pr.draft else "merged" if merged else state)
    return Footer(emoji, f"PR #{pr.number}: {pr.title}")


def pr_embed_content(
    pr: PRLike, template: str, body: str | None = None
) -> EmbedContent:
    return EmbedContent(template.format(f"PR #{pr.number}"), pr.html_url, body)


@client.on("pull_request")
async def handle_pr_event(event: PullRequestEvent) -> None:
    if subhook := pr_subhooks.get(event.action):
        with reraise_with_payload(event):
            await subhook(event)


@final
class PRHook(commands.Cog):
    def __init__(self, bot: GhosttyBot, monalisten_client: Monalisten) -> None:
        self.bot = bot
        self.monalisten_client = monalisten_client

    @override
    async def cog_load(self) -> None:
        @self.monalisten_client.on("pull_request_review_comment")
        async def _(event: PullRequestReviewCommentEvent) -> None:
            if event.action == "created":
                with reraise_with_payload(event):
                    await self.handle_pr_review_comment_created(event)

        @self.monalisten_client.on("pull_request_review")
        async def _(event: PullRequestReviewEvent) -> None:
            if subhook := pr_review_subhooks.get(event.action):
                with reraise_with_payload(event):
                    await subhook(event)

    @register_pr_subhook("opened")
    async def handle_opened_pr(self, event: WebhookPullRequestOpened) -> None:
        pr = event.pull_request
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "opened {}", pr.body),
            pr_footer(pr, emoji="pull_open"),
            color="green",
        )

    @register_pr_subhook("closed")
    async def handle_closed_pr(self, event: WebhookPullRequestClosed) -> None:
        pr = event.pull_request
        action, color = ("merged", "purple") if pr.merged else ("closed", "red")
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, f"{action} {{}}"),
            pr_footer(pr, emoji="pull_" + action),
            color=color,
        )

    @register_pr_subhook("reopened")
    async def handle_reopened_pr(self, event: WebhookPullRequestReopened) -> None:
        pr = event.pull_request
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "reopened {}"),
            pr_footer(pr, emoji="pull_open"),
            color="green",
        )

    @register_pr_subhook("edited")
    async def handle_edited_pr(self, event: WebhookPullRequestEdited) -> None:
        pr, changes = event.pull_request, event.changes

        if pr.created_at > dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=15):
            return

        update_notes: list[str] = []
        if changes.title:
            update_notes.append(f'Renamed from "{changes.title.from_}" to "{pr.title}"')
        if changes.body:
            update_notes.append("Updated description")

        match update_notes:
            case [note]:
                content = note
            case [note1, note2]:
                content = f"* {note1}\n* {note2}"
            case _:
                return

        assert event.sender
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "edited {}", content),
            pr_footer(pr),
        )

    @register_pr_subhook("converted_to_draft")
    async def handle_drafted_pr(
        self, event: WebhookPullRequestConvertedToDraft
    ) -> None:
        pr = event.pull_request
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "converted {} to draft"),
            pr_footer(pr, emoji="pull_draft"),
            color="gray",
        )

    @register_pr_subhook("ready_for_review")
    async def handle_undrafted_pr(
        self, event: WebhookPullRequestReadyForReview
    ) -> None:
        pr = event.pull_request
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "marked {} as ready for review"),
            pr_footer(pr, emoji="pull_open"),
            color="green",
        )

    @register_pr_subhook("locked")
    async def handle_locked_pr(self, event: WebhookPullRequestLocked) -> None:
        pr = event.pull_request
        template = "locked {}"
        if reason := pr.active_lock_reason:
            template += f" as {reason}"
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, template),
            pr_footer(pr),
            color="orange",
        )

    @register_pr_subhook("unlocked")
    async def handle_unlocked_pr(self, event: WebhookPullRequestUnlocked) -> None:
        pr = event.pull_request
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "unlocked {}"),
            pr_footer(pr),
            color="blue",
        )

    @register_pr_subhook("review_requested")
    async def handle_pr_review_request(
        self, event: WebhookPullRequestReviewRequested
    ) -> None:
        pr = event.pull_request
        content = f"from {self._format_reviewer(event)}"
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "requested review for {}", content),
            pr_footer(pr),
        )

    @register_pr_subhook("review_request_removed")
    async def handle_pr_removed_review_request(
        self, event: WebhookPullRequestReviewRequestRemoved
    ) -> None:
        pr = event.pull_request
        content = f"from {self._format_reviewer(event)}"
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(pr, "removed review request for {}", content),
            pr_footer(pr),
        )

    # Abusing `Any`/`getattr`/`hasattr` here because the API models are insufferable
    @staticmethod
    def _format_reviewer(event: Any) -> str:
        if hasattr(event, "requested_team"):
            return f"the `{event.requested_team.name}` team"
        if requested_reviewer := getattr(event, "requested_reviewer", None):
            return GitHubUser(**requested_reviewer.model_dump()).hyperlink
        return "`?`"

    @register_pr_review_subhook("submitted")
    async def handle_pr_review_submitted(
        self, event: WebhookPullRequestReviewSubmitted
    ) -> None:
        pr, review = event.pull_request, event.review

        if review.state == "commented" and not review.body:
            # We most definitely have some pull_request_review_comment event(s)
            # happening at the same time, so an empty review like this can be ignored
            # to reduce spam.
            return

        match review.state:
            case "approved":
                color, title = "green", "approved"
            case "commented":
                color, title = None, "reviewed"
            case "changes_requested":
                color, title = "red", "requested changes in"
            case s:
                logger.warning("unexpected review state: {}", s)
                return

        emoji = "pull_" + (
            "draft" if pr.draft else "merged" if pr.merged_at else pr.state
        )
        await send_embed(
            self.bot,
            event.sender,
            EmbedContent(f"{title} PR #{pr.number}", review.html_url, review.body),
            pr_footer(pr, emoji=emoji),
            color=color,
        )

    @register_pr_review_subhook("dismissed")
    async def handle_pr_review_dismissed(
        self, event: WebhookPullRequestReviewDismissed
    ) -> None:
        pr = event.pull_request
        emoji = "pull_" + (
            "draft" if pr.draft else "merged" if pr.merged_at else pr.state
        )
        review_author = (
            GitHubUser(**event.review.user.model_dump())
            if event.review.user
            else GitHubUser.default()
        )
        await send_embed(
            self.bot,
            event.sender,
            pr_embed_content(
                pr, "dismissed a {} review", f"authored by {review_author.hyperlink}"
            ),
            pr_footer(pr, emoji=emoji),
            color="orange",
        )

    async def handle_pr_review_comment_created(
        self, event: WebhookPullRequestReviewCommentCreated
    ) -> None:
        pr, content = event.pull_request, event.comment.body

        hunk = self._reduce_diff_hunk(event.comment.diff_hunk)
        if 500 - len(content) - len(hunk) - HUNK_CODEBLOCK_OVERHEAD >= 0:
            # We can fit a hunk!
            content = f"```diff\n{hunk}\n```\n{content}"

        await send_embed(
            self.bot,
            event.sender,
            EmbedContent(
                f"left a review comment on PR #{pr.number}",
                event.comment.html_url,
                content,
            ),
            pr_footer(pr, from_review=True),
        )

    def _reduce_diff_hunk(self, hunk: str) -> str:
        def missing_diff_marker(line: str) -> bool:
            return not line.startswith(("-", "+"))

        hunk_lines = [*dropwhile(missing_diff_marker, hunk.splitlines())]
        return "\n".join([*dropwhile(missing_diff_marker, hunk_lines[::-1])][::-1])
