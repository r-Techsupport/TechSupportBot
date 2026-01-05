"""
TO HANDLE:
- Reactions
- Threads
- Embeds
- Channel Info
- Discriminator (for bot accounts)
"""

from __future__ import annotations

import json
import zipfile
from datetime import timezone
from pathlib import Path
from typing import Self

import bot
import discord
from core import cogs
from discord import app_commands

ARCHIVE_DIR = Path("/archive-output")


async def setup(bot: bot.TechSupportBot) -> None:
    await bot.add_cog(ChannelTextArchiver(bot=bot))


class ChannelTextArchiver(cogs.BaseCog):

    async def write_channel_archive_zip(
        self: Self,
        channel: discord.TextChannel | discord.Thread,
        filename: str,
    ) -> Path:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = ARCHIVE_DIR / filename

        authors_seen: set[int] = set()

        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zip_file:
            async for message in channel.history(
                limit=None,
                oldest_first=True,
            ):
                message_id = str(message.id)
                message_folder = f"Messages/{message_id}/"

                author = message.author
                username = author.name
                author_id = author.id

                if author_id not in authors_seen:
                    authors_seen.add(author_id)

                    author_data = {
                        "id": str(author.id),
                        "name": author.name,
                        "display_name": author.display_name,
                        "global_name": author.global_name,
                        "display_color": f"#{author.color.value:06x}",
                    }

                    zip_file.writestr(
                        f"Authors/{author_id}/author.json",
                        json.dumps(author_data, indent=2, ensure_ascii=False),
                    )

                    if author.display_avatar:
                        avatar_bytes = await author.display_avatar.read()
                        zip_file.writestr(
                            f"Authors/{author_id}/profile-pic.png",
                            avatar_bytes,
                        )

                reply_data = None

                if message.reference and isinstance(
                    message.reference.resolved,
                    discord.Message,
                ):
                    ref = message.reference.resolved
                    reply_data = {
                        "reply_id": str(ref.id),
                        "reply_deleted": False,
                        "reply_content": ref.clean_content,
                        "reply_author": ref.author.name,
                    }
                elif message.reference:
                    reply_data = {
                        "reply_id": str(message.reference.message_id),
                        "reply_deleted": True,
                        "reply_content": None,
                        "reply_author": None,
                    }

                message_data = {
                    "id": message_id,
                    "content": message.clean_content,
                    "timestamp": message.created_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                    "author_username": username,
                    "attachments": [
                        f"{idx}-{a.filename}"
                        for idx, a in enumerate(message.attachments, start=1)
                    ],
                }

                if reply_data is not None:
                    message_data["reply"] = reply_data

                zip_file.writestr(
                    f"{message_folder}message.json",
                    json.dumps(message_data, indent=2, ensure_ascii=False),
                )

                attachments_folder = f"{message_folder}attachments/"

                for idx, attachment in enumerate(message.attachments, start=1):
                    data = await attachment.read()
                    safe_name = f"{idx}-{attachment.filename}"

                    zip_file.writestr(
                        f"{attachments_folder}{safe_name}",
                        data,
                    )

        return zip_path

    @app_commands.command(
        name="archive",
        description="Archive messages, authors, attachments, and replies",
    )
    async def archive_text(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(thinking=True)

        zip_path = await self.write_channel_archive_zip(
            channel=interaction.channel,
            filename=f"{interaction.channel.id}_archive.zip",
        )

        await interaction.followup.send(
            f"Archive completed successfully.\nSaved to `{zip_path}`"
        )
