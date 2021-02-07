import datetime

import cogs
import discord
import emoji
import sqlalchemy
from discord.ext import commands


def setup(bot):
    bot.add_cog(ChannelDirectory(bot))


# can you think of a better name?
class DirectoryExistence(cogs.DatabasePlugin.get_base()):
    __tablename__ = "directoryexistence"
    guild_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    last_message = sqlalchemy.Column(sqlalchemy.String, default=None)


class ChannelDirectory(cogs.DatabasePlugin):

    PLUGIN_NAME = __name__

    # I refuse to install num2word
    OPTION_EMOJIS = [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
    ]
    MODEL = DirectoryExistence
    DIR_ICON_URL = "https://cdn.icon-icons.com/icons2/1585/PNG/512/3709735-application-contact-directory-phonebook-storage_108083.png"

    async def preconfig(self):
        self.message_ids = set()
        self.option_map = {}

        db = self.db_session()
        self.option_emojis = [
            emoji.emojize(f":{emoji_text}:", use_aliases=True)
            for emoji_text in self.OPTION_EMOJIS
        ]

        for guild_id in self.config.keys():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            channel_id = self.config.get(guild_id, {}).get("directory_channel")
            if not channel_id:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            exists = True
            existence = (
                db.query(DirectoryExistence)
                .filter(
                    DirectoryExistence.guild_id == str(guild_id),
                )
                .first()
            )
            if not existence:
                # no record in table
                # create new object
                exists = False
                existence = DirectoryExistence(guild_id=str(guild_id))
                message_id = None
            else:
                # there is a record
                # try to get its message ID keeping in mind it's stored as str
                try:
                    message_id = int(existence.last_message)
                except ValueError:
                    # nothing we can do, move on
                    continue

            message = (
                discord.utils.get(
                    await channel.history(limit=100).flatten(), id=message_id
                )
                if message_id
                else None
            )
            if message:
                await message.delete()

            new_message = await self.send_embed(
                self.config.get(guild_id, {}).get("channel_map"), guild, channel
            )

            existence.last_message = str(new_message.id)
            self.message_ids.add(new_message.id)

            if not exists:
                db.add(existence)

            db.commit()

        db.close()

    async def send_embed(self, channel_map, guild, directory_channel):
        embed = self.bot.embed_api.Embed(
            title="Channel Directory",
            description="Once selecting a channel, you will be given the role to access it. You can come back here to remove the role or add more roles at any time",
        )

        embed.set_thumbnail(url=self.DIR_ICON_URL)

        message = await directory_channel.send("Loading channel directory...")

        for index, channel_id in enumerate(channel_map):
            channel = self.bot.get_channel(channel_id)
            if not channel or not channel.topic:
                continue

            role_name = channel_map.get(channel_id)
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue

            self.option_map[self.option_emojis[index]] = role

            embed.add_field(
                name=f"{self.option_emojis[index]} #{channel.name}",
                value=channel.topic,
                inline=False,
            )

            await message.add_reaction(self.option_emojis[index])

        await message.edit(content=None, embed=embed)

        return message

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        if not reaction.message.id in self.message_ids:
            return

        role = self.option_map.get(reaction.emoji)
        if not role:
            return

        await user.add_roles(role)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        if not reaction.message.id in self.message_ids:
            return

        role = self.option_map.get(reaction.emoji)
        if not role:
            return

        await user.remove_roles(role)
