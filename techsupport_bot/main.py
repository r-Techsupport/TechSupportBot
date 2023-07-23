"""TechSupport Bot main thread.
"""
import asyncio
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
asyncio.run(bot_.start())
