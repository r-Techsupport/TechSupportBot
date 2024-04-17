"""Module for the dumpdbg command on discord bot."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the DumpDBG plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.dumpdbg:
            raise AttributeError("Dumpdbg was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Dumpdbg was not loaded due to missing API key") from exc

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="roles",
        datatype="list",
        title="Permitted roles",
        description="Roles permitted to use this command",
        default=["super op"],
    )

    await bot.add_cog(Dumpdbg(bot=bot))
    bot.add_extension_config("dumpdbg", config)


class Dumpdbg(cogs.BaseCog):
    """Class for the dump debugger on the discord bot."""

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        name="dumpdbg",
        aliases=["dump", "debug-dump", "debug_dump", "debugdump"],
        brief="Debugs an uploaded dump file",
        description=(
            "Runs an attached Windows minidump (.dmp) files through WinDBG on "
            "an external server and returns the pasted output."
        ),
        usage="|attached-dump-files|",
    )
    async def debug_dump(self: Self, ctx: commands.Context) -> None:
        """The entry point and main logic for the dump debug command

        Args:
            ctx (commands.Context): The context in which the command was run
        """

        config = self.bot.guild_configs[str(ctx.guild.id)]
        api_endpoint = self.bot.file_config.api.api_url.dumpdbg
        permitted_roles = config.extensions.dumpdbg.roles.value

        if not permitted_roles:
            await auxiliary.send_deny_embed(
                message="No permitted roles set in the config!", channel=ctx.channel
            )
            return

        # -> Message checks <-

        # Checks if the user has any permitted roles
        if not any(role.name in permitted_roles for role in ctx.message.author.roles):
            return

        valid_URLs = await self.get_files(ctx)

        if len(valid_URLs) == 0:
            await auxiliary.send_deny_embed(
                message="No valid attached dump files detected!", channel=ctx.channel
            )
            return

        # Reaction to indicate a succesful request
        await ctx.message.add_reaction("⏱️")

        # -> API checks <-

        # Makes sure the API key was suplied

        KEY = self.bot.file_config.api.api_keys.dumpdbg

        if KEY in (None, ""):
            await auxiliary.send_deny_embed(
                message="No API key found!", channel=ctx.channel
            )
            return

        # -> API call(s) <-

        result_urls = []  # Used to get the string for the returned message

        for dump_url in valid_URLs:
            data = {
                "key": KEY,
                "url": dump_url,
            }

            # API Call itself
            json_data = json.dumps(data).encode("utf-8")

            # Makes sure api endpoint doesn't use file:// etc (Codefactor B310)
            if not api_endpoint.lower().startswith("http"):
                await auxiliary.send_deny_embed(
                    message="API endpoint not HTTP/HTTPS", channel=ctx.channel
                )
                return

            response = await self.bot.http_functions.http_call(
                "post",
                api_endpoint,
                data=json_data,
                headers={"Content-Type": "application/json"},
            )

            # Handling for failed results
            if response["success"] is False:
                await auxiliary.send_deny_embed(
                    message="Something went wrong with debugging! "
                    + f"Api response: `{response['error']}`",
                    channel=ctx.channel,
                )
                channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=(
                        f"Dumpdbg API responded with the error `{response['error']}`"
                    ),
                    level=LogLevel.WARNING,
                    channel=channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )
                return
            result_urls.append(response["url"])

        # -> Message returning <-
        # Converted to str outside of bottom code because f-strings can't contain backslashes

        # Formatting for several files because it looks prettier
        if len(result_urls) == 1:
            await ctx.send(
                embed=auxiliary.generate_basic_embed(
                    title="Dump succesfully debugged! \nResult links:",
                    description="\n".join(result_urls),
                    color=discord.Color.green(),
                ),
                content=auxiliary.construct_mention_string([ctx.author]),
            )
        else:
            await ctx.send(
                embed=auxiliary.generate_basic_embed(
                    title="Dumps succesfully debugged! \nResult links:",
                    description="\n".join(result_urls),
                    color=discord.Color.green(),
                )
            )

    async def get_files(self: Self, ctx: commands.Context) -> list[str]:
        """Gets files from passed message and checks if they are valid .dmp files

        Args:
            ctx (commands.Context): The message to check

        Returns:
            list[str]: The list of valid .dmp CDN links
        """

        # Checks if attachments were supplied
        if len(ctx.message.attachments) == 0:
            return []

        # -> Getting valid dump files <-

        valid_URLs = []  # File CDN URLs to PUT to the API for debugging
        dump_no = 0  # Used for error message

        # Checks attachments for dump files, disregards 0 byte dumps
        for attachment in ctx.message.attachments:
            if attachment.filename.endswith(".dmp"):
                dump_no += 1
                #  Disregards any empty dumps
                if attachment.size == 0:
                    await ctx.send(
                        embed=auxiliary.generate_basic_embed(
                            title="Invalid dump detected (Size 0)",
                            description=f"Skipping dump number {dump_no}...",
                            color=discord.Color.green(),
                        )
                    )
                    continue

                valid_URLs.append(attachment.url)
        return valid_URLs
