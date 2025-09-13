import asyncio
from contextlib import suppress

from app import log
from app.bot import GhosttyBot
from app.config import config, gh


async def main() -> None:
    log.setup(config)

    async with GhosttyBot(config, gh) as bot:
        await bot.start(config.token.get_secret_value())


with suppress(KeyboardInterrupt):
    asyncio.run(main())
