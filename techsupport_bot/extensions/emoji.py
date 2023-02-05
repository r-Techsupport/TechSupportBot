import base
import discord
import emoji
import inflect
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(Emojis(bot=bot))


class Emojis(base.BaseCog):
    SEARCH_LIMIT = 20
    KEY_MAP = {"?": "question", "!": "exclamation"}

    @classmethod
    def emoji_from_char(cls, char):
        if char.isalpha():
            return emoji.emojize(
                f":regional_indicator_symbol_letter_{char.lower()}:", use_aliases=True
            )
        if char.isnumeric():
            char = inflect.engine().number_to_words(char)
            return emoji.emojize(f":{char}:", use_aliases=True)
        if cls.KEY_MAP.get(char):
            return emoji.emojize(f":{cls.KEY_MAP[char]}:", use_aliases=True)

    @classmethod
    def emoji_message_from_string(cls, string):
        emoji_message = ""
        registered = False
        for char in string:
            emoji_ = cls.emoji_from_char(char)
            if emoji_:
                emoji_message += emoji_ + " "
                registered = True
            else:
                emoji_message += char + " "
        if not emoji_message or not registered:
            return None
        return emoji_message

    @classmethod
    def emoji_reaction_from_string(cls, string):
        found = {}
        emoji_list = []
        for char in string:
            if char == " ":
                continue
            if found.get(char):
                return None
            emoji_ = cls.emoji_from_char(char)
            if emoji_:
                emoji_list.append(emoji_)
                found[char] = True
            else:
                return None
        if not emoji_list:
            return None
        return emoji_list

    @commands.group(
        brief="Executes an emoji command",
        description="Executes a emoji command",
    )
    async def emoji(self, ctx):
        pass

    @util.with_typing
    @emoji.command(
        aliases=["msg"],
        brief="Generates an emoji message",
        description="Creates a regional_indiciator_X emoji message",
        usage="[message]",
    )
    async def message(self, ctx, *, message: str):
        emoji_message = self.emoji_message_from_string(message)
        if not emoji_message:
            await ctx.send_deny_embed(
                "I can't get any emoji letters from your message!"
            )
            return

        await ctx.send(emoji_message)

    @commands.has_permissions(add_reactions=True)
    @commands.guild_only()
    @emoji.command(
        brief="Reacts with emojis",
        description="Creates a regional_indiciator_X emoji reaction for a user's most recent message",
        usage="[message] @user",
    )
    async def reaction(self, ctx, message: str, react_user: discord.Member):
        prefix = await self.bot.get_prefix(ctx.message)

        react_message = None
        async for channel_message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if (
                channel_message.author == react_user
                and not channel_message.content.startswith(prefix)
            ):
                react_message = channel_message
                break
        if not react_message:
            await ctx.send_deny_embed("No valid messages found to react to!")
            return

        emoji_list = self.emoji_reaction_from_string(message)
        if not emoji_list:
            await ctx.send_deny_embed(
                "Invalid message! Make sure there are no repeat characters!"
            )
            return

        for emoji_ in emoji_list:
            await react_message.add_reaction(emoji_)
