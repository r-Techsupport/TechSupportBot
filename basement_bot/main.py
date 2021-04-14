"""Basement Bot main thread.
"""
import bot
import discord
import logging

OVERRIDDEN_MODULES_MAP = {
    "discord": logging.INFO,
    "gino": logging.WARNING,
    "aio_pika": logging.INFO,
}

for module_name, level in OVERRIDDEN_MODULES_MAP.items():
    logging.getLogger(module_name).setLevel(level)

intents = discord.Intents.default()
intents.members = True

bot_ = bot.BasementBot(intents=intents)
