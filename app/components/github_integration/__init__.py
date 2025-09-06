import asyncio
from typing import TYPE_CHECKING

from .mentions import fmt as fmt
from app.errors import handle_task_error

if TYPE_CHECKING:
    from app.bot import GhosttyBot


async def setup(bot: "GhosttyBot") -> None:
    from .code_links import CodeLinks
    from .comments import CommentIntegration
    from .commits import Commits
    from .emoji import load_emojis
    from .mentions import MentionIntegration
    from .webhooks import Discussions, Issues, PRHook, monalisten_client

    await load_emojis(bot)

    await bot.add_cog(Discussions(bot, monalisten_client))
    await bot.add_cog(Issues(bot, monalisten_client))
    await bot.add_cog(PRHook(bot, monalisten_client))

    await bot.add_cog(Commits(bot, monalisten_client))
    await bot.add_cog(CodeLinks(bot))
    await bot.add_cog(MentionIntegration(bot))
    await bot.add_cog(CommentIntegration(bot))

    monalisten_task = asyncio.create_task(monalisten_client.listen())
    monalisten_task.add_done_callback(handle_task_error)
    bot.background_tasks.add(monalisten_task)
