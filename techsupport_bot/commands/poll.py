"""Module for the poll extension for the discord bot."""

from __future__ import annotations

import asyncio
import io
import json
from typing import TYPE_CHECKING, Self

import discord
import emoji
import munch
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Poller plugins into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(ReactionPoller(bot=bot))
    await bot.add_cog(StrawPoller(bot=bot))


class PollGenerator(cogs.BaseCog):
    """Class to make the poll generator for the extension."""

    async def validate_data(
        self: Self,
        ctx: commands.Context,
        request_body: munch.Munch,
        strawpoll: bool = False,
    ) -> munch.Munch:
        """Validates the uploaded json to ensure that the poll is valid.
        Will potentially make changes to some aspects to ensure that everything works
            such as timeout

        Args:
            ctx (commands.Context): The context in which the command was run
            request_body (munch.Munch): The uploaded json of the created poll
            strawpoll (bool, optional): If this should be a strawpoll or a reaction poll.
                Defaults to False.

        Returns:
            munch.Munch: The validated and updated (if needed) config for the poll.
        """
        # probably shouldn't touch this
        max_options = len(self.OPTION_EMOJIS) if not strawpoll else 10

        question = request_body.get("question")
        options = request_body.get("options", [])
        image_url = request_body.get("image_url")
        timeout = request_body.get("timeout")

        if not question:
            await auxiliary.send_deny_embed(
                message="I did not find a poll question (`question` key)",
                channel=ctx.channel,
            )
            return None
        if not isinstance(question, str):
            await auxiliary.send_deny_embed(
                message="I need the poll question to be a string (`question` key)",
                channel=ctx.channel,
            )
            return None

        if not isinstance(options, list):
            await auxiliary.send_deny_embed(
                message="I need the poll options to be a list (`options` key)",
                channel=ctx.channel,
            )
            return None
        if len(options) < 2 or len(options) > max_options:
            await auxiliary.send_deny_embed(
                message=f"I need between 2 and {max_options} options! (`options` key)",
                channel=ctx.channel,
            )
            return None

        if not strawpoll:
            if not image_url or not isinstance(image_url, str):
                request_body.image_url = (
                    "https://cdn.icon-icons.com/icons2"
                    "/259/PNG/128/ic_poll_128_28553.png"
                )

            if not timeout or not isinstance(timeout, int):
                request_body.timeout = 60
            elif request_body.timeout > 300:
                request_body.timeout = 300
            elif request_body.timeout < 10:
                request_body.timeout = 10

        return request_body


class ReactionPoller(PollGenerator):
    """Class to add reactions to the poll generator.

    Attrs:
        OPTION_EMOJIS (list[str]): The list of emojis to react to the message with
        STOP_EMOJI (str): The stop emoji to reaction to the message with
        EXAMPLE_DATA (dict[str, str | list[str] | int]): The example poll that the bot can use

    """

    OPTION_EMOJIS = ["one", "two", "three", "four", "five"]
    STOP_EMOJI = "\u26d4"
    EXAMPLE_DATA = {
        "question": "Best ice cream?",
        "options": ["Chocolate", "Vanilla", "Strawberry", "Cookie Dough", "Other..."],
        "timeout": 60,
    }

    async def preconfig(self: Self) -> None:
        """Method to preconfig the poll."""
        self.option_emojis = [
            emoji.emojize(f":{emoji_text}:", language="alias")
            for emoji_text in self.OPTION_EMOJIS
        ]

    @commands.group(
        brief="Executes a poll command",
        description="Executes a poll command",
    )
    async def poll(self: Self, ctx: commands.Context) -> None:
        """The bare .poll command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @poll.command(
        brief="Shows example poll JSON",
        description="Shows what JSON to upload to generate a poll",
    )
    async def example(self: Self, ctx: commands.Context) -> None:
        """Method to show an example of a poll.

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        json_file = discord.File(
            io.StringIO(json.dumps(self.EXAMPLE_DATA, indent=4)),
            filename="poll_example.json",
        )
        await ctx.send(file=json_file)

    @auxiliary.with_typing
    @commands.guild_only()
    @poll.command(
        aliases=["create"],
        brief="Generates a poll",
        description=(
            "Creates a poll for everyone to vote in (only admins can make polls)"
        ),
        usage="|json-upload|",
    )
    async def generate(self: Self, ctx: commands.Context) -> None:
        """Method to generate the poll for discord.

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        request_body = await auxiliary.get_json_from_attachments(ctx.message)
        if not request_body:
            await auxiliary.send_deny_embed(
                message="I couldn't find any data in your upload", channel=ctx.channel
            )
            return

        request_body = await self.validate_data(ctx, request_body)
        if not request_body:
            return

        message = await auxiliary.send_confirm_embed(
            message="Poll loading...", channel=ctx.channel
        )

        display_timeout = (
            request_body.timeout
            if request_body.timeout <= 60
            else request_body.timeout // 60
        )
        display_timeout_units = "seconds" if request_body.timeout <= 60 else "minutes"

        embed = auxiliary.generate_basic_embed(
            title=request_body.question,
            description=f"Poll timeout: {display_timeout} {display_timeout_units}",
            color=discord.Color.gold(),
            url=request_body.image_url,
        )

        for index, option in enumerate(request_body.options):
            embed.add_field(name=option, value=index + 1, inline=False)
            await message.add_reaction(self.option_emojis[index])

        await message.edit(content=None, embed=embed)

        results = await self.wait_for_results(
            ctx, message, request_body.timeout, request_body.options
        )
        if results is None:
            await auxiliary.send_deny_embed(
                message="I ran into an issue grabbing the poll results...",
                channel=ctx.channel,
            )
            try:
                await message.edit(content="*Poll aborted!*", embed=None)
                await message.clear_reactions()
            except discord.NotFound:
                await auxiliary.send_deny_embed(
                    message=(
                        "I could not find the poll message. It might have been deleted?"
                    ),
                    channel=ctx.channel,
                )
            except discord.Forbidden:
                pass
            return

        total = sum(count for count in results.values())
        if total == 0:
            await auxiliary.send_deny_embed(
                message=(
                    "Nobody voted in the poll, so I won't bother showing any results"
                ),
                channel=ctx.channel,
            )
            return

        embed = auxiliary.generate_basic_embed(
            title=f"Poll results for `{request_body.question}`",
            description=f"Votes: {total}",
            color=discord.Color.gold(),
            thumbnail_url=request_body.image_url,
        )

        for option, count in results.items():
            percentage = str((count * 100) // total)
            embed.add_field(name=option, value=f"{percentage}%", inline=False)

        await ctx.send(embed=embed)

    async def wait_for_results(
        self: Self,
        ctx: commands.Context,
        message: discord.Message,
        timeout: int,
        options: list[str],
    ) -> dict[str, int]:
        """Waits for the poll to conclude, and then gets the results

        Args:
            ctx (commands.Context): The context in which the command was run in
            message (discord.Message): The message containing the reaction poll
            timeout (int): The amount of seconds the reaction poll should run for
            options (list[str]): The list of the options for the poll

        Returns:
            dict[str, int]: The options list with the amount of votes for each option
        """
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

                if user.id not in excluded:
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
    """Class to create a straw poll from discord.

    Attrs:
        EXAMPLE_DATA (dict[str, str | list[str]]): The example poll that the bot can use
        API_URL (str): The strawpoll API URL

    """

    EXAMPLE_DATA = {
        "question": "Best ice cream?",
        "options": ["Chocolate", "Vanilla", "Strawberry", "Cookie Dough", "Other..."],
    }
    API_URL = "https://strawpoll.com/api/poll"

    @commands.group(
        brief="Executes a strawpoll command",
        description="Executes a strawpoll command",
    )
    async def strawpoll(self: Self, ctx: commands.Context) -> None:
        """Method to give an exmaple poll with json.

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @strawpoll.command(
        brief="Shows example poll JSON",
        description="Shows what JSON to upload to generate a poll",
    )
    async def example(self: Self, ctx: commands.Context) -> None:
        """Method that contains the example file for a poll.

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        json_file = discord.File(
            io.StringIO(json.dumps(self.EXAMPLE_DATA, indent=4)),
            filename="poll_example.json",
        )
        await ctx.send(file=json_file)

    @auxiliary.with_typing
    @strawpoll.command(
        brief="Generates a strawpoll",
        description="Returns a link to a Strawpoll generated by args",
        usage="|json-upload|",
    )
    async def generate(self: Self, ctx: commands.Context) -> None:
        """Method to generate the poll form the discord command.

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        request_body = await auxiliary.get_json_from_attachments(ctx.message)
        if not request_body:
            await auxiliary.send_deny_embed(
                message="I couldn't find any data in your upload", channel=ctx.channel
            )
            return

        request_body = await self.validate_data(ctx, request_body, strawpoll=True)
        if not request_body:
            return

        post_body = {
            "poll": {"title": request_body.question, "answers": request_body.options}
        }

        response = await self.bot.http_functions.http_call(
            "post", self.API_URL, json=post_body
        )

        content_id = response.get("content_id")
        if not content_id:
            await auxiliary.send_deny_embed(
                message="Strawpoll did not let me create a poll", channel=ctx.channel
            )
            return

        await auxiliary.send_confirm_embed(
            message=f"https://strawpoll.com/{content_id}", channel=ctx.channel
        )
