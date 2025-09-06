import asyncio

from app import log
from app.bot import GhosttyBot
from app.config import config, gh


async def main() -> None:
    log.setup(config)

    # Our logging is handled by Loguru, and logs from the standard logging module are
    # forwarded to Loguru in setup.py; hence, disable discord.py's log handler to avoid
    # duplicated logs showing up in stderr.
    async with GhosttyBot(config, gh) as bot:
        await bot.start(config.token.get_secret_value())


asyncio.run(main())
