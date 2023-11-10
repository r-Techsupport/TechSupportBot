"""
A listener which changes peoples nicknames on join
The cog in the file is named:
    AutoNickName

This file does not contain any commands
"""

import random
import re
import string

import discord
from base import cogs
from botlogging import LogContext, LogLevel
from unidecode import unidecode


async def setup(bot):
    """Registers the AutoNickName Cog"""
    await bot.add_cog(AutoNickName(bot=bot))


class AutoNickName(cogs.BaseCog):
    def format_username(self, username: str) -> str:
        """Formats a username to be all ascii and easily readable and pingable

        Args:
            username (str): The original users username

        Returns:
            str: The new username with all formatting applied
        """

        # Prepare a random string, just in case
        random_string = "".join(random.choice(string.ascii_letters) for _ in range(10))

        # Step 1 - Force all ascii
        username = unidecode(username)

        # Step 2 - Remove all markdown
        markdown_pattern = r"(\*\*|__|\*|_|\~\~|`|#+|-{3,}|\|{3,}|>)"
        username = re.sub(markdown_pattern, "", username)

        # Step 3 - Strip
        username = username.strip()

        # Step 4 - Fix dumb spaces
        username = re.sub(r"\s+", " ", username)
        username = re.sub(r"(\b\w) ", r"\1", username)

        # Step 5 - Start with letter
        match = re.search(r"[A-Za-z]", username)
        if match:
            username = username[match.start() :]
        else:
            username = ""

        # Step 6 - Length check
        if len(username) < 3 and len(username) > 0:
            username = f"{username}-USER-{random_string}"
        elif len(username) == 0:
            username = f"USER-{random_string}"
        username = username[:32]

        return username

    async def on_member_join(self, member: discord.Member) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""
        config = self.guild_configs[str(member.guild.id)]

        if config.get("nickname_filter", False):
            temp_name = self.format_username(member.display_name)
            if temp_name != member.display_name:
                await member.edit(nick=temp_name)
                try:
                    await member.send(
                        "Your nickname has been changed to make it easy to read and"
                        f" ping your name. Your new nickname is {temp_name}."
                    )
                except discord.Forbidden:
                    channel = config.get("logging_channel")
                    await self.logger.send_log(
                        message=f"Could not DM {member.name} about nickname changes",
                        level=LogLevel.WARNING,
                        channel=channel,
                        context=LogContext(guild=member.guild),
                    )
