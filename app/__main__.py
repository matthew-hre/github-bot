import sentry_sdk

from app.core import bot, config

if config.sentry_dsn is not None:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Our logging is handled by Loguru, and logs from the standard logging module are
# forwarded to Loguru in setup.py; hence, disable discord.py's log handler to avoid
# duplicated logs showing up in stderr.
bot.run(config.token, log_handler=None)
