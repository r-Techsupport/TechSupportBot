import asyncio
import datetime

import cogs
import decorate
import discord
import emoji
from discord.ext import commands


def setup(bot):
    bot.add_cog(Poller(bot))


class Poller(cogs.BasicPlugin):

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
        "timeout": 60,
    }"""

    async def preconfig(self):
        self.option_emojis = [
            emoji.emojize(f":{emoji_text}:", use_aliases=True)
            for emoji_text in self.OPTION_EMOJIS
        ]

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="poll",
        brief="Poll generator",
        description="Creates a poll for everyone to vote in (only admins can make polls)",
        usage="help",
    )
    async def generate_poll(self, ctx, *args):
        if len(args) != 0 and args[0] == "help":
            await self.bot.h.tagged_response(
                ctx, f"Upload a JSON like this: ```{self.EXAMPLE_JSON}```"
            )
            return

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.author.send("I cannot create a poll in a DM")
            return

        request_body = await self.bot.h.get_json_from_attachment(ctx, ctx.message)
        if not request_body:
            return

        request_body = await self.validate_data(ctx, request_body)
        if not request_body:
            return

        message = await self.bot.h.tagged_response(ctx, "Poll loading...")

        # TODO: actually not be lazy and write float formatting for the time left
        display_timeout = (
            request_body.timeout
            if request_body.timeout <= 60
            else request_body.timeout // 60
        )
        display_timeout_units = "seconds" if request_body.timeout <= 60 else "minutes"

        embed = self.bot.embed_api.Embed(
            title=request_body.question,
            description=f"Poll timeout: {display_timeout} {display_timeout_units}",
        )
        embed.set_thumbnail(url=request_body.image_url)

        for index, option in enumerate(request_body.options):
            embed.add_field(name=option, value=index + 1, inline=False)
            await message.add_reaction(self.option_emojis[index])

        await message.edit(content=None, embed=embed)

        results = await self.wait_for_results(
            ctx, message, request_body.timeout, request_body.options
        )
        if results is None:
            await self.bot.h.tagged_response(
                ctx, "I ran into an issue grabbing the poll results..."
            )
            try:
                await message.edit(content="*Poll aborted!*", embed=None)
                await message.clear_reactions()
            except discord.NotFound:
                await self.bot.h.tagged_response(
                    ctx,
                    "I could not find the poll message. It might have been deleted?",
                )
            except discord.Forbidden:
                pass
            return

        total = sum(count for count in results.values())
        if total == 0:
            await self.bot.h.tagged_response(
                ctx, "Nobody voted in the poll, so I won't bother showing any results"
            )
            return

        embed = self.bot.embed_api.Embed(
            title=f"Poll results for `{request_body.question}`",
            description=f"Votes: {total}",
        )
        embed.set_thumbnail(url=request_body.image_url)

        for option, count in results.items():
            percentage = str((count * 100) // total)
            embed.add_field(name=option, value=f"{percentage}%", inline=False)

        await self.bot.h.tagged_response(ctx, embed=embed)

    async def wait_for_results(self, ctx, message, timeout, options):
        option_emojis = self.option_emojis[: len(options)]
        await asyncio.sleep(timeout)

        # count the votes after the poll finishes
        voted = {}
        excluded = set()
        cached_message = discord.utils.get(ctx.bot.cached_messages, id=message.id)
        if not cached_message:
            return None

        for reaction in cached_message.reactions:
            async for user in reaction.users():
                if user.bot:
                    continue

                if voted.get(user.id):
                    # delete their vote and exclude them from the count
                    del voted[user.id]
                    excluded.add(user.id)

                if not user.id in excluded:
                    try:
                        voted[user.id] = options[option_emojis.index(reaction.emoji)]
                    except ValueError:
                        pass

        await message.delete()

        unique_votes = list(voted.values())
        # I thought of this myself
        results = {option: unique_votes.count(option) for option in set(unique_votes)}

        # this ensures even the 0 votes show up
        for option in options:
            if not results.get(option):
                results[option] = 0

        return results

    async def validate_data(self, ctx, request_body):
        # probably shouldn't touch this
        max_options = len(self.OPTION_EMOJIS)

        question = request_body.get("question")
        options = request_body.get("options", [])
        image_url = request_body.get("image_url")
        timeout = request_body.get("timeout")

        if not question:
            await self.bot.h.tagged_response(
                ctx, "I did not find a poll question (`question` key)"
            )
            return None
        elif not isinstance(question, str):
            await self.bot.h.tagged_response(
                ctx, "I need the poll question to be a string (`question` key)"
            )
            return None

        if not isinstance(options, list):
            await self.bot.h.tagged_response(
                ctx, "I need the poll options to be a list (`question` key)"
            )
            return None
        elif len(options) < 2 or len(options) > max_options:
            await self.bot.h.tagged_response(
                ctx, f"I need between 2 and {max_options} options! (`options` key)"
            )
            return None

        if not image_url or not isinstance(image_url, str):
            request_body.image_url = (
                "https://cdn.icon-icons.com/icons2/259/PNG/128/ic_poll_128_28553.png"
            )

        if not timeout or not isinstance(timeout, int):
            request_body.timeout = 60
        elif request_body.timeout > 300:
            request_body.timeout = 300
        elif request_body.timeout < 10:
            request_body.timeout = 10

        return request_body
