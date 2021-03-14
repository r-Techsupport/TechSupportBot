import datetime

import cogs
import decorate
import discord
import emoji
import sqlalchemy
from discord.ext import commands


def setup(bot):
    class DirectoryExistence(bot.db.Model):
        __tablename__ = "directoryexistence"
        guild_id = bot.db.Column(bot.db.String, primary_key=True)
        last_message = bot.db.Column(bot.db.String, default=None)

    config = bot.PluginConfig()
    config.add(
        key="channel",
        datatype="int",
        title="Directory Channel ID",
        description="The ID of the channel to run the directory in",
        default=None,
    )
    config.add(
        key="channel_role_map",
        datatype="dict",
        title="Channel ID to Role mapping",
        description="A mapping of channel ID's to role names",
        default={},
    )

    return bot.process_plugin_setup(
        cogs=[ChannelDirectory], models=[DirectoryExistence], config=config
    )


class ChannelDirectory(cogs.BaseCog):

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
    DIR_ICON_URL = "https://cdn.icon-icons.com/icons2/1585/PNG/512/3709735-application-contact-directory-phonebook-storage_108083.png"

    async def preconfig(self):
        self.message_ids = set()
        self.option_map = {}

        self.option_emojis = [
            emoji.emojize(f":{emoji_text}:", use_aliases=True)
            for emoji_text in self.OPTION_EMOJIS
        ]

        for guild in self.bot.guilds:
            await self.run_setup(guild)

    async def run_setup(self, guild):
        config = await self.bot.get_context_config(ctx=None, guild=guild)

        channel_id = config.plugins.directory.channel.value
        if not channel_id:
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return

        channel_map = config.plugins.directory.channel_role_map.value
        if not channel_map:
            return

        existence = await self.models.DirectoryExistence.query.where(
            self.models.DirectoryExistence.guild_id == str(guild.id)
        ).gino.first()
        if not existence:
            # no record in table
            # create new object
            existence = await self.models.DirectoryExistence(
                guild_id=str(guild.id)
            ).create()
            message_id = None
        else:
            # there is a record
            # try to get its message ID keeping in mind it's stored as str
            try:
                message_id = int(existence.last_message)
            except ValueError:
                # nothing we can do, move on
                return

        message = (
            discord.utils.get(await channel.history(limit=100).flatten(), id=message_id)
            if message_id
            else None
        )
        if message:
            await message.delete()

        new_message = await self.send_embed(channel_map, guild, channel)

        await existence.update(last_message=str(new_message.id)).apply()

        self.message_ids.add(new_message.id)

    async def send_embed(self, channel_map, guild, directory_channel):
        embed = self.bot.embed_api.Embed(
            title="Channel Directory",
            description="Once selecting a channel, you will be given the role to access it. You can come back here to remove the role or add more roles at any time",
        )

        embed.set_thumbnail(url=self.DIR_ICON_URL)

        message = await directory_channel.send("Loading channel directory...")

        self.option_map[guild.id] = {}

        for index, channel_id in enumerate(channel_map):
            channel = self.bot.get_channel(int(channel_id))
            if not channel or not channel.topic:
                continue

            role_name = channel_map.get(channel_id)
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue

            self.option_map[guild.id][self.option_emojis[index]] = role

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

        role = self.option_map.get(reaction.message.guild.id, {}).get(reaction.emoji)
        if not role:
            return

        await user.add_roles(role)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        if not reaction.message.id in self.message_ids:
            return

        role = self.option_map.get(reaction.message.guild.id, {}).get(reaction.emoji)
        if not role:
            return

        await user.remove_roles(role)

    @commands.group(
        brief="Executes a directory command",
        description="Executes a directory command",
    )
    async def directory(self, ctx):
        pass

    @decorate.with_typing
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @directory.command(
        brief="Rerun directory setup",
        description="Reruns the directory setup for the current guild",
    )
    async def rerun(self, ctx):
        await self.run_setup(ctx.guild)
