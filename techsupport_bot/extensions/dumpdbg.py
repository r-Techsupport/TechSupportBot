"""Module for the dumpdbg command on discord bot."""
import json
import urllib.parse
import urllib.request

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    """Method to add burn command to config."""
    config = bot.ExtensionConfig()
    config.add(
        key="api_ip",
        datatype="str",
        title="DBG Server IP",
        description="IP For the server running WinDBG accessed via an API",
        default="",
    )
    config.add(
        key="roles",
        datatype="list",
        title="Permitted roles",
        description="Roles permitted to use this command",
        default=["super op"],
    )

    bot.add_cog(Dumpdbg(bot=bot))
    bot.add_extension_config("Dumpdbg", config)


class DumpdbgEmbed(discord.Embed):
    """Class to set up the dumpdbg embed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()


class Dumpdbg(base.BaseCog):
    """Class for the dump debugger on the discord bot."""

    async def call_api(self, protocol, url, data):
        """Method to get the results from the api.
        Params:
        -> protocol (str): Http protocol to use for the call
        -> url (str): URL to send the request to
        -> data (dict): Data to send"""
        response = await self.bot.http_call(protocol, url, params=data, use_cache=True)
        return response

    @util.with_typing
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.channel)
    @commands.command(
        name="dumpdbg",
        aliases=["dump", "debug-dump", "debug_dump", "debugdump"],
        brief="Debugs an uploaded dump file",
        description="Runs an uploaded Windows minidump through WinDBG on \
            an external server and returns the pasted output.",
    )
    async def debug_dump(self, ctx):
        """Method for the actual debugging"""

        # -> Message checks <-

        config = await self.bot.get_context_config(guild=ctx.guild)
        api_ip = config.extensions.Dumpdbg.api_ip.value
        permitted_roles = config.extensions.Dumpdbg.roles.value

        # Checks if the user has any permitted roles
        if not any(role.name in permitted_roles for role in ctx.message.author.roles):
            return

        # Checks if attachments were supplied
        if len(ctx.message.attachments) == 0:
            await ctx.send_deny_embed("No file supplied!")
            return

        # -> Getting valid dump files <-

        valid_URLs = []  # File CDN URLs to PUT to the API for parsing
        dump_valid = 0  # Number of valid files

        # Checks attachments for dump files, disregards 0 byte dumps
        for attachment in ctx.message.attachments:
            if attachment.filename.endswith(".dmp"):
                # Disregards any empty dumps
                if attachment.size == 0:
                    await ctx.send(
                        embed=DumpdbgEmbed(
                            title="Invalid dump detected (Size 0)",
                            description=f"Dump number {dump_valid}, skipping...",
                        )
                    )
                    continue

                dump_valid += 1
                valid_URLs.append(attachment.url)

        if dump_valid == 0:
            await ctx.send_deny_embed("No valid dumps detected!")
            return

        # -> API checks <-

        # Makes sure the API key was suplied
        try:
            KEY = self.bot.file_config.main.api_keys.dumpdbg_api
        except AttributeError:
            await ctx.send_deny_embed("No API key found!")
            return

        # -> API call(s) <-

        # Try except used because the API key can be present in the request URL,
        # this is addressed by making sure it isn't posted to a public channel.
        try:
            result_urls = []  # Used to get the string for the returned message

            for dump_url in valid_URLs:
                data = {
                    "key": KEY,
                    "url": dump_url,
                }

                # API Call itself
                json_data = json.dumps(data).encode("utf-8")
                if api_ip.startswith("http"):
                    req = urllib.request.Request(
                        api_ip, json_data, headers={"Content-Type": "application/json"}
                    )
                    response = json.loads(
                        urllib.request.urlopen(req, timeout=100).read().decode("utf-8")
                    )
                else:
                    raise ValueError("API endpoint not HTTP/HTTPS")

                # Handling for failed results
                if response["success"] == "false":
                    await ctx.send_deny_embed(
                        f"Something went wrong with debugging! Error: {response['error']}"
                    )
                    await self.logger.error(
                        f"Dumpdbg API responded with the error `{response['error']}`"
                    )
                    return

                # Handling for succesful results
                result_urls.append(response["url"])

            # -> Message returning <-
            # Converted to str outside of bottom code because f-strings can't contain backslashes
            result_urls = "\n".join(result_urls)

            # Formatting for several files because it looks prettier
            if len(result_urls) == 1:
                await ctx.send(
                    embed=DumpdbgEmbed(
                        title="Dump succesfully debugged! \nResult links:",
                        description=result_urls,
                    )
                )
            else:
                await ctx.send(
                    embed=DumpdbgEmbed(
                        title="Dumps succesfully debugged! \nResult links:",
                        description=result_urls,
                    )
                )

        except Exception as e:
            await ctx.send_deny_embed("Exception thrown from command!")
            print(f"Dumpdbg API exception thrown! Exception: {e}")
