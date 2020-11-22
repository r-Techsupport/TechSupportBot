import asyncio

from cogs import BasicPlugin
from discord import Embed, Forbidden, NotFound
from discord import utils as discord_utils
from discord.channel import DMChannel
from discord.ext import commands
from emoji import emojize
from utils.helpers import *


def setup(bot):
    bot.add_cog(Poller(bot))


class Poller(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    OPTION_EMOJIS = ["one", "two", "three", "four", "five"]
    STOP_EMOJI = "\u26D4"
    EXAMPLE_JSON = """
    {
        "question": "Best ice cream",
        "options": [
            "Chocolate",
            "Vanilla",
            "Strawberry",
            "Cookie Dough",
            "Other..."
        ],
        "timeout": 5,
    }"""

    async def preconfig(self):
        self.option_emojis = [
            emojize(f":{emoji_text}:", use_aliases=True)
            for emoji_text in self.OPTION_EMOJIS
        ]

    @commands.check(is_admin)
    @commands.command(name="poll")
    async def generate_poll(self, ctx, *args):
        if len(args) != 0 and args[0] == "help":
            await tagged_response(
                ctx, f"Upload a JSON like this: ```{self.EXAMPLE_JSON}```"
            )
            return

        if isinstance(ctx.channel, DMChannel):
            await priv_response(ctx, "I cannot create a poll in a DM")
            return

        request_body = await get_json_from_attachment(ctx, ctx.message)
        if not request_body:
            return

        request_body = await self.validate_data(ctx, request_body)

        message = await tagged_response(ctx, "Poll loading...")

        # TODO: actually not be lazy and write float formatting for the time left
        display_timeout = (
            request_body.timeout
            if request_body.timeout <= 60
            else request_body.timeout // 60
        )
        display_timeout_units = "seconds" if request_body.timeout <= 60 else "minutes"

        embed = Embed(
            title=request_body.question,
            description=f"Poll ends in {display_timeout} {display_timeout_units}",
        )
        embed.set_thumbnail(url=request_body.image_url)

        for index, option in enumerate(request_body.options):
            embed.add_field(name=option, value=index + 1, inline=False)
            await message.add_reaction(self.option_emojis[index])
        # stop button reaction
        await message.add_reaction(self.STOP_EMOJI)

        await message.edit(content=None, embed=embed)

        results = await self.wait_for_results(
            ctx, message, request_body.timeout, request_body.options
        )
        if results is None:
            await priv_response(ctx, "I ran into an issue grabbing the poll results...")
            try:
                await message.edit(content="*Poll aborted!*", embed=None)
                await message.clear_reactions()
            except NotFound:
                await priv_response(
                    ctx,
                    "I could not find the poll message. It might have been deleted?",
                )
            except Forbidden:
                pass
            return
        elif results == {}:
            await priv_response(
                ctx, "Nobody voted in the poll, so I won't bother showing any results"
            )
            return

        total = sum(count for count in results.values())
        embed = Embed(
            title=f"Poll results for `{request_body.question}`",
            description=f"Votes: {total}",
        )
        embed.set_thumbnail(url=request_body.image_url)

        for option, count in results.items():
            percentage = str((count * 100) // total)
            embed.add_field(name=option, value=f"{percentage}%", inline=False)

        await tagged_response(ctx, embed=embed)

    async def wait_for_results(self, ctx, message, timeout, options):
        voted = {}
        message_id = message.id
        while True:
            try:
                reaction, user = await ctx.bot.wait_for(
                    "reaction_add", timeout=timeout, check=lambda r, u: not bool(u.bot)
                )
            except Exception:
                break

            if reaction.message.id != message_id:
                continue

            # stop button check
            elif reaction.emoji == self.STOP_EMOJI and user.id == ctx.message.author.id:
                # return None
                break

            elif not reaction.emoji in self.option_emojis:
                try:
                    await reaction.remove(user)
                except Forbidden:
                    return None
                continue

            try:
                # simple
                vote = options[self.option_emojis.index(reaction.emoji)]
            except ValueError:
                return None

            voted[user.id] = vote

        await message.delete()

        unique_votes = list(voted.values())
        # I thought of this myself
        return {option: unique_votes.count(option) for option in set(unique_votes)}

    async def validate_data(self, ctx, request_body):
        # probably shouldn't touch this
        max_options = len(self.OPTION_EMOJIS)

        question = request_body.get("question")
        options = request_body.get("options", [])
        image_url = request_body.get("image_url")
        timeout = request_body.get("timeout")

        if not question:
            await priv_response(ctx, "No poll question provided! (`name` key)")
            return
        if len(options) < 2 or len(options) > max_options:
            await priv_response(
                ctx, f"I need between 2 and {max_options} questions! (`questions` key)"
            )
            return
        if not image_url:
            request_body.image_url = (
                "https://cdn.icon-icons.com/icons2/259/PNG/128/ic_poll_128_28553.png"
            )
        if not timeout:
            request_body.timeout = 60
        elif request_body.timeout > 300:
            request_body.timeout = 300
        elif request_body.timeout < 10:
            request_body.timeout = 10

        return request_body
