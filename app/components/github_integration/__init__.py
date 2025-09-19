from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .code_links import CodeLinks
from .comments import Comments
from .commits import Commits
from .mentions import Mentions
from .mentions import fmt as fmt
from .webhooks import Discussions, Issues, PRs, monalisten_client
from app.errors import handle_task_error

if TYPE_CHECKING:
    from app.bot import GhosttyBot


async def setup(bot: GhosttyBot) -> None:
    await asyncio.gather(
        bot.add_cog(Discussions(bot, monalisten_client)),
        bot.add_cog(Issues(bot, monalisten_client)),
        bot.add_cog(PRs(bot, monalisten_client)),
        bot.add_cog(Commits(bot, monalisten_client)),
        bot.add_cog(CodeLinks(bot)),
        bot.add_cog(Mentions(bot)),
        bot.add_cog(Comments(bot)),
    )

    # Creating a strong reference
    monalisten_task = asyncio.create_task(monalisten_client.listen())
    monalisten_task.add_done_callback(handle_task_error)
    bot.background_tasks.add(monalisten_task)
