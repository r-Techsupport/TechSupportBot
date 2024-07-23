"""The file that holds the paste function"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Self

import discord
import munch
from botlogging import LogContext, LogLevel
from core import cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(Paster(bot=bot))


class Paster(cogs.MatchCog):
    """The pasting module"""

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
        """Checks to see if a message should be considered for a paste

        Args:
            config (munch.Munch): The config of the guild to check
            ctx (commands.Context): The context of the original message
            content (str): The string representation of the message

        Returns:
            bool: Whether the message should be inspected for a paste
        """
        # exit the match based on exclusion parameters
        if not str(ctx.channel.id) in config.extensions.protect.channels.value:
            await self.bot.logger.send_log(
                message="Channel not in protected channels - ignoring protect check",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.extensions.protect.bypass_roles.value
        ):
            return False

        if ctx.author.id in config.extensions.protect.bypass_ids.value:
            return False

        return True

    async def response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        result: bool,
    ) -> None:
        """Handles a paste check

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (bool): What the match() function returned
        """
        if len(content) > config.extensions.protect.length_limit.value or content.count(
            "\n"
        ) > self.max_newlines(config.extensions.protect.length_limit.value):
            await self.handle_length_alert(config, ctx, content)

    def max_newlines(self: Self, max_length: int) -> int:
        """Gets a theoretical maximum number of new lines in a given message

        Args:
            max_length (int): The max length of characters per theoretical line

        Returns:
            int: The maximum number of new lines based on config
        """
        return int(max_length / 80) + 1

    @commands.Cog.listener()
    async def on_raw_message_edit(
        self: Self, payload: discord.RawMessageUpdateEvent
    ) -> None:
        """This is called when any message is edited in any guild the bot is in.
        There is no guarantee that the message exists or is used

        Args:
            payload (discord.RawMessageUpdateEvent): The raw event that the edit generated
        """
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = self.bot.guild_configs[str(guild.id)]
        if not self.extension_enabled(config):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        # Don't trigger if content hasn't changed
        if payload.cached_message and payload.cached_message.content == message.content:
            return

        ctx = await self.bot.get_context(message)
        matched = await self.match(config, ctx, message.content)
        if not matched:
            return

        await self.response(config, ctx, message.content, None)

    async def handle_length_alert(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> None:
        """Moves message into a linx paste if it's too long

        Args:
            config (munch.Munch): The guild config where the too long message was sent
            ctx (commands.Context): The context where the original message was sent
            content (str): The string content of the flagged message
        """
        attachments: list[discord.File] = []
        if ctx.message.attachments:
            total_attachment_size = 0
            for attch in ctx.message.attachments:
                if (
                    total_attachment_size := total_attachment_size + attch.size
                ) <= ctx.filesize_limit:
                    attachments.append(await attch.to_file())
            if (lf := len(ctx.message.attachments) - len(attachments)) != 0:
                log_channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=(
                        f"Protect did not reupload {lf} file(s) due to file size limit."
                    ),
                    level=LogLevel.WARNING,
                    channel=log_channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )
        await ctx.message.delete()

        reason = "message too long (too many newlines or characters)"

        if not self.bot.file_config.api.api_url.linx:
            await self.send_default_delete_response(config, ctx, content, reason)
            return

        linx_embed = await self.create_linx_embed(config, ctx, content)
        if not linx_embed:
            await self.send_default_delete_response(config, ctx, content, reason)
            # await self.send_alert(config, ctx, "Could not convert text to Linx paste")
            return

        await ctx.send(
            ctx.message.author.mention, embed=linx_embed, files=attachments[:10]
        )

    async def send_default_delete_response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        reason: str,
    ) -> None:
        """Sends a DM to a user containing a message that was deleted

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context of the deleted message
            content (str): The context of the deleted message
            reason (str): The reason the message was deleted
        """
        embed = discord.Embed(
            title="Chat Protection", description=f"Message deleted. Reason: *{reason}*"
        )
        embed.color = discord.Color.gold()
        await ctx.send(ctx.message.author.mention, embed=embed)
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def create_linx_embed(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> discord.Embed | None:
        """This function sends a message to the linx url and puts the result in
        an embed to be sent to the user

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context that generated the need for a paste
            content (str): The context of the message to be pasted

        Returns:
            discord.Embed | None: The formatted embed, or None if there was an API error
        """
        if not content:
            return None

        headers = {
            "Linx-Expiry": "1800",
            "Linx-Randomize": "yes",
            "Accept": "application/json",
        }
        html_file = {"file": io.StringIO(content)}
        response = await self.bot.http_functions.http_call(
            "post",
            self.bot.file_config.api.api_url.linx,
            headers=headers,
            data=html_file,
        )

        url = response.get("url")
        if not url:
            return None

        embed = discord.Embed(description=url)

        embed.add_field(name="Paste Link", value=url)
        embed.description = content[0:100].replace("\n", " ")
        embed.set_author(
            name=f"Paste by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )
        embed.set_footer(text=config.extensions.protect.paste_footer_message.value)
        embed.color = discord.Color.blue()

        return embed
