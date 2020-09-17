from discord.ext import commands
from emoji import EMOJI_UNICODE, emojize
from inflect import engine as inflect_engine

from cogs import BasicPlugin
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(LetterEmojis(bot))


class LetterEmojis(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 20

    @staticmethod
    def emoji_from_char(char):
        if char.isalpha():
            return emojize(
                f":regional_indicator_symbol_letter_{char.lower()}:", use_aliases=True
            )
        if char.isnumeric():
            char = inflect_engine().number_to_words(char)
            return emojize(f":{char}:", use_aliases=True)

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

    @commands.command(
        name="emsg",
        brief="H E L L O!",
        description="Creates a regional_indiciator_X emoji message.",
        usage="[message]",
    )
    async def emsg(self, ctx, *args):
        if ctx.message.mentions:
            await priv_response(ctx, "I can't make an emoji from a mention!")
            return

        message = " ".join(args) if args else None
        if not message:
            await priv_response(ctx, "You must specify a message!")
            return

        emoji_message = self.emoji_message_from_string(message)
        if emoji_message:
            await tagged_response(ctx, emoji_message)
        else:
            await priv_response(ctx, "I can't get any emoji letters from your message!")

    @commands.command(
        name="ermsg",
        brief="H E L O! but as a reaction...",
        description="Creates a regional_indiciator_X emoji reaction for a user's most recent message.",
        usage="[message] @user",
    )
    async def ermsg(self, ctx, *args):
        message = " ".join(args[:-1]) if args else None
        if not message:
            await priv_response(ctx, "You must specify a message!")
            return

        if not len(ctx.message.mentions) == 1:
            await priv_response(ctx, "You must mention a specific user to react to!")
            return
        react_user = ctx.message.mentions[0]

        react_message = None
        async for channel_message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if (
                channel_message.author == react_user
                and not channel_message.content.startswith(
                    f"{self.bot.config.main.required.command_prefix}"
                )
            ):
                react_message = channel_message
                break
        if not react_message:
            await priv_response(ctx, f"No valid messages found to react to!")
            return

        emoji_list = self.emoji_reaction_from_string(message)
        if not emoji_list:
            await priv_response(
                ctx, "Invalid message! Make sure there are no repeat letters!"
            )
            return

        for emoji_ in emoji_list:
            await react_message.add_reaction(emoji_)
