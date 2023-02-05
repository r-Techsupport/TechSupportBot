import asyncio
import io
import json

import base
import discord
import emoji
import util
from discord.ext import commands
from discord.reaction import Reaction


def setup(bot):
    bot.add_cog(ReactionPoller(bot=bot))
    bot.add_cog(StrawPoller(bot=bot))


class PollEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        thumbnail_url = kwargs.pop("thumbnail_url")
        super().__init__(*args, **kwargs)
        self.set_thumbnail(url=thumbnail_url)
        self.color = discord.Color.gold()


class PollGenerator(base.BaseCog):
    async def validate_data(self, ctx, request_body, strawpoll=False):
        # probably shouldn't touch this
        max_options = len(self.OPTION_EMOJIS) if not strawpoll else 10

        question = request_body.get("question")
        options = request_body.get("options", [])
        image_url = request_body.get("image_url")
        timeout = request_body.get("timeout")

        if not question:
            await ctx.send_deny_embed("I did not find a poll question (`question` key)")
            return None
        elif not isinstance(question, str):
            await ctx.send_deny_embed(
                "I need the poll question to be a string (`question` key)"
            )
            return None

        if not isinstance(options, list):
            await ctx.send_deny_embed(
                "I need the poll options to be a list (`question` key)"
            )
            return None
        elif len(options) < 2 or len(options) > max_options:
            await ctx.send_deny_embed(
                f"I need between 2 and {max_options} options! (`options` key)"
            )
            return None

        if not strawpoll:
            if not image_url or not isinstance(image_url, str):
                request_body.image_url = "https://cdn.icon-icons.com/icons2/259/PNG/128/ic_poll_128_28553.png"

            if not timeout or not isinstance(timeout, int):
                request_body.timeout = 60
            elif request_body.timeout > 300:
                request_body.timeout = 300
            elif request_body.timeout < 10:
                request_body.timeout = 10

        return request_body


class ReactionPoller(PollGenerator):

    OPTION_EMOJIS = ["one", "two", "three", "four", "five"]
    STOP_EMOJI = "\u26D4"
    EXAMPLE_DATA = {
        "question": "Best ice cream?",
        "options": ["Chocolate", "Vanilla", "Strawberry", "Cookie Dough", "Other..."],
        "timeout": 60,
    }

    async def preconfig(self):
        self.option_emojis = [
            emoji.emojize(f":{emoji_text}:", use_aliases=True)
            for emoji_text in self.OPTION_EMOJIS
        ]

    @commands.group(
        brief="Executes a poll command",
        description="Executes a poll command",
    )
    async def poll(self, ctx):
        pass

    @util.with_typing
    @poll.command(
        brief="Shows example poll JSON",
        description="Shows what JSON to upload to generate a poll",
    )
    async def example(self, ctx):
        json_file = discord.File(
            io.StringIO(json.dumps(self.EXAMPLE_DATA, indent=4)),
            filename="poll_example.json",
        )
        await ctx.send(file=json_file)

    @util.with_typing
    @commands.guild_only()
    @poll.command(
        aliases=["create"],
        brief="Generates a poll",
        description="Creates a poll for everyone to vote in (only admins can make polls)",
        usage="|json-upload|",
    )
    async def generate(self, ctx):
        request_body = await util.get_json_from_attachments(ctx.message)
        if not request_body:
            await ctx.send_deny_embed("I couldn't find any data in your upload")
            return

        request_body = await self.validate_data(ctx, request_body)
        if not request_body:
            return

        message = await ctx.send_confirm_embed("Poll loading...")

        display_timeout = (
            request_body.timeout
            if request_body.timeout <= 60
            else request_body.timeout // 60
        )
        display_timeout_units = "seconds" if request_body.timeout <= 60 else "minutes"

        embed = PollEmbed(
            title=request_body.question,
            description=f"Poll timeout: {display_timeout} {display_timeout_units}",
            thumbnail_url=request_body.image_url,
        )

        for index, option in enumerate(request_body.options):
            embed.add_field(name=option, value=index + 1, inline=False)
            await message.add_reaction(self.option_emojis[index])

        await message.edit(content=None, embed=embed)

        results = await self.wait_for_results(
            ctx, message, request_body.timeout, request_body.options
        )
        if results is None:
            await ctx.send_deny_embed(
                "I ran into an issue grabbing the poll results..."
            )
            try:
                await message.edit(content="*Poll aborted!*", embed=None)
                await message.clear_reactions()
            except discord.NotFound:
                await ctx.send_deny_embed(
                    "I could not find the poll message. It might have been deleted?",
                )
            except discord.Forbidden:
                pass
            return

        total = sum(count for count in results.values())
        if total == 0:
            await ctx.send_deny_embed(
                "Nobody voted in the poll, so I won't bother showing any results"
            )
            return

        embed = PollEmbed(
            title=f"Poll results for `{request_body.question}`",
            description=f"Votes: {total}",
            thumbnail_url=request_body.image_url,
        )

        for option, count in results.items():
            percentage = str((count * 100) // total)
            embed.add_field(name=option, value=f"{percentage}%", inline=False)

        await ctx.send(embed=embed)

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


class StrawPoller(PollGenerator):

    EXAMPLE_DATA = {
        "question": "Best ice cream?",
        "options": ["Chocolate", "Vanilla", "Strawberry", "Cookie Dough", "Other..."],
    }
    API_URL = "https://strawpoll.com/api/poll"

    @commands.group(
        brief="Executes a strawpoll command",
        description="Executes a strawpoll command",
    )
    async def strawpoll(self, ctx):
        print(f"Strawpoll command called in channel {ctx.channel}")

    @util.with_typing
    @strawpoll.command(
        brief="Shows example poll JSON",
        description="Shows what JSON to upload to generate a poll",
    )
    async def example(self, ctx):
        json_file = discord.File(
            io.StringIO(json.dumps(self.EXAMPLE_DATA, indent=4)),
            filename="poll_example.json",
        )
        await ctx.send(file=json_file)

    @util.with_typing
    @strawpoll.command(
        brief="Generates a strawpoll",
        description="Returns a link to a Strawpoll generated by args",
        usage="|json-upload|",
    )
    async def generate(self, ctx):
        request_body = await util.get_json_from_attachments(ctx.message)
        if not request_body:
            await ctx.send_deny_embed("I couldn't find any data in your upload")
            return

        request_body = await self.validate_data(ctx, request_body, strawpoll=True)
        if not request_body:
            return

        post_body = {
            "poll": {"title": request_body.question, "answers": request_body.options}
        }

        response = await self.bot.http_call("post", self.API_URL, json=post_body)

        content_id = response.get("content_id")
        if not content_id:
            await ctx.send_deny_embed("Strawpoll did not let me create a poll")
            return

        await ctx.send_confirm_embed(f"https://strawpoll.com/{content_id}")
