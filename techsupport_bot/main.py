"""TechSupport Bot main thread."""

import logging
import os

import bot
import discord

MODULE_LOG_LEVELS = {
    "discord": logging.INFO,
    "gino": logging.WARNING,
}

for module_name, level in MODULE_LOG_LEVELS.items():
    logging.getLogger(module_name).setLevel(level)

try:
    debug_mode = bool(int(os.environ.get("DEBUG", 0)))
except TypeError:
    debug_mode = False

logging.basicConfig(
    level=logging.DEBUG if debug_mode else logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

intents = discord.Intents.all()
intents.members = True

bot_ = bot.TechSupportBot(
    intents=intents,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
)
# Creates & starts a custom event loop for the bot, because Modmail runs its own one as well and
# you can not run nested asyncio loops

bot.loop.create_task(bot_.start())
bot.loop.run_forever()
