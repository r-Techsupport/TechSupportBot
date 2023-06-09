"""Module for the dumpdbg command on discord bot."""
import json

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add the dumpdbg command to config."""
    config = bot.ExtensionConfig()
    config.add(
        key="api_endpoint",
        datatype="str",
        title="DBG Server API address",
        description="Endpoint for WinDBG server",
        default="",
    )
    config.add(
        key="roles",
        datatype="list",
        title="Permitted roles",
        description="Roles permitted to use this command",
        default=["super op"],
    )

    await bot.add_cog(Dumpdbg(bot=bot))
    bot.add_extension_config("dumpdbg", config)


class DumpdbgEmbed(discord.Embed):
    """Class to set up the dumpdbg embed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()


class Dumpdbg(base.BaseCog):
    """Class for the dump debugger on the discord bot."""

    @util.with_typing
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.channel)
    @commands.command(
        name="dumpdbg",
        aliases=["dump", "debug-dump", "debug_dump", "debugdump"],
        brief="Debugs an uploaded dump file",
        description="Runs an attached Windows minidump (.dmp) files through WinDBG on \
            an external server and returns the pasted output.",
        usage="|attached-dump-files|",
    )
    async def debug_dump(self, ctx):
        """Method for the actual debugging"""

        async def get_files(ctx):
            """Gets files from passed message and checks if they are valid .dmp files

            Params:
              -> ctx (discord.Context) = The message to check

            Returns:
              -> Valid_URLs (list) = The list of valid .dmp CDN links
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
                            embed=DumpdbgEmbed(
                                title="Invalid dump detected (Size 0)",
                                description=f"Skipping dump number {dump_no}...",
                            )
                        )
                        continue

                    valid_URLs.append(attachment.url)
            return valid_URLs

        config = await self.bot.get_context_config(guild=ctx.guild)
        api_endpoint = config.extensions.dumpdbg.api_endpoint.value
        permitted_roles = config.extensions.dumpdbg.roles.value

        # -> Message checks <-

        # Checks if the user has any permitted roles
        if not any(role.name in permitted_roles for role in ctx.message.author.roles):
            return

        valid_URLs = await get_files(ctx)

        if len(valid_URLs) == 0:
            await auxiliary.send_deny_embed(
                message="No valid attached dump files detected!", channel=ctx.channel
            )
            return

        # Reaction to indicate a succesful request
        await ctx.message.add_reaction("⏱️")

        # -> API checks <-

        # Makes sure the API key was suplied

        KEY = self.bot.file_config.main.api_keys.dumpdbg_api

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

            response = await self.bot.http_call(
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
                await self.bot.logger.warning(
                    f"Dumpdbg API responded with the error `{response['error']}`"
                )
                return
            result_urls.append(response["url"])

        # -> Message returning <-
        # Converted to str outside of bottom code because f-strings can't contain backslashes

        # Formatting for several files because it looks prettier
        if len(result_urls) == 1:
            await ctx.send(
                embed=DumpdbgEmbed(
                    title="Dump succesfully debugged! \nResult links:",
                    description="\n".join(result_urls),
                )
            )
        else:
            await ctx.send(
                embed=DumpdbgEmbed(
                    title="Dumps succesfully debugged! \nResult links:",
                    description="\n".join(result_urls),
                )
            )
