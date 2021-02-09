"""Basement Bot main thread.
"""
import bot
import discord

intents = discord.Intents.default()
intents.members = True

bot_ = bot.BasementBot()
