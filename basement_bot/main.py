"""Basement Bot main thread.
"""
import logging

import bot
import discord

OVERRIDDEN_MODULES_MAP = {
    "discord": logging.INFO,
    "gino": logging.WARNING,
    "aio_pika": logging.INFO,
}

for module_name, level in OVERRIDDEN_MODULES_MAP.items():
    logging.getLogger(module_name).setLevel(level)

intents = discord.Intents.default()
intents.members = True

# plugins can override this manually
# this avoids general ping abuse of plugins
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False)

bot_ = bot.BasementBot(intents=intents, allowed_mentions=allowed_mentions)
