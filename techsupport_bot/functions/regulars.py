
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Union


import datetime
from datetime import datetime

import discord
import munch
from botlogging import LogContext, LogLevel
from core import cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot

async def setup(bot):
    # Config needed:
    # Regular role to manage
    # How many messages must be sent in a 7 day period
    # How many days must at least one message be sent
    # How long do you have to meet regular requirements to get the role
    # How long do you have to fail regular requirements to lose the role
    await bot.add_cog(RegularTracking(bot=bot, extension_name="regulars"))


class RegularTracking(cogs.MatchCog):

    async def match(self, config: munch.Munch, ctx: commands.Context, _) -> bool:
        if ctx.author.bot:
            return False
        return True

    async def response(self, config: munch.Munch, ctx: commands.Context, _, __) -> None:
        # print(f"{ctx.author} sent a message")
        print(f"DAY: {self.get_day_number()}")

    def get_day_number(self) -> int:
        return datetime.today().weekday()
    
    async def update_database(self, day: int, member: discord.Member):
        entry = await self.get_user_entry_in_database(member)
        if day == 0:
            print("A")
            # do stuff

    async def get_user_entry_in_database(self, member: discord.Member) -> bot.models.RegularTracking:
        query = self.bot.models.RegularTracking.query.where(
            self.bot.models.RegularTracking.user_id == str(member.id)
        ).where(self.bot.models.RegularTracking.guild_id == str(member.guild.id))
        entry = await query.gino.first()
        if not entry:
            return await self.create_new_entry_in_database(member)
        return entry

    async def create_new_entry_in_database(self, member: discord.Member) -> bot.models.RegularTracking:
        tracking = self.bot.models.RegularTracking(
            guild_id=str(member.guild.id),
            user_id=str(member.id),
        )

        await tracking.create()
        return tracking