import logging

from cogs import BasicPlugin
from discord.ext import commands
from utils.embed import SafeEmbed
from utils.helpers import *


def setup(bot):
    bot.add_cog(Mocker(bot))


class Mocker(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 20

    @staticmethod
    def mock_string(string):
        mock = ""
        i = True
        for char in string:
            if i:
                mock += char.upper()
            else:
                mock += char.lower()
            if char != " ":
                i = not i
        return mock

    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="sb",
        brief="MOcKS last MeSSAgE Of MeNtIONeD uSEr",
        description=(
            "Returns last message of mentioned user following command changing"
            " random characters to capital or lowercase."
        ),
        usage="[mentioned-user]",
        help=(
            "\nLimitations: Ignores any additional mentions after the command"
            " and first mentioned user."
        ),
    )
    async def mock(self, ctx):
        user_to_mock = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_mock:
            await tagged_response(ctx, "You must tag a user if you want to mock them!")
            return

        if user_to_mock.bot:
            user_to_mock = ctx.author

        mock_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_mock and not message.content.startswith(
                self.bot.config.main.required.command_prefix
            ):
                mock_message = message.content
                break

        if not mock_message:
            await tagged_response(ctx, f"No message found for user {user_to_mock}")
            return

        filtered_message = sub_mentions_for_usernames(ctx.bot, mock_message)
        mock_string = self.mock_string(filtered_message)
        embed = SafeEmbed(title=f'"{mock_string}"', description=user_to_mock.name)
        embed.set_thumbnail(url=user_to_mock.avatar_url)

        await tagged_response(ctx, embed=embed)
