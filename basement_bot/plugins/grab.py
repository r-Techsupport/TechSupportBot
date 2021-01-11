import datetime
from random import randint

from cogs import DatabasePlugin
from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String, desc
from utils.embed import SafeEmbed
from utils.helpers import *


class Grab(DatabasePlugin.BaseTable):
    __tablename__ = "grabs"

    pk = Column(Integer, primary_key=True)
    author_id = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)


def setup(bot):
    bot.add_cog(Grabber(bot))


class Grabber(DatabasePlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 20
    MODEL = Grab

    async def invalid_channel(self, ctx):
        if isinstance(ctx.channel, DMChannel):
            await priv_response(ctx, "I can't grab a message in a DM!")
            return False

        if ctx.channel.id in self.config.invalid_channels:
            await tagged_response(ctx, "Grabs are disabled for this channel")
            return False

        return True

    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="grab",
        brief="Grab the last message from the mentioned user",
        description=(
            "Gets the last message of the mentioned user and saves it"
            " in the database for later retrieval."
        ),
        usage="[mentioned-user]",
        help=(
            "\nLimitations: The command will only look for a mentioned user."
            " Any additional plain text, other mentioned users, or @here/@everyone"
            " will be ignored."
        ),
    )
    async def grab(self, ctx):
        if self.invalid_channel(ctx):
            return

        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_grab:
            await tagged_response(ctx, "You must tag a user to grab!")
            return

        if user_to_grab.bot:
            await tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        grab_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab and not message.content.startswith(
                f"{self.bot.config.main.required.command_prefix}grab"
            ):
                grab_message = message.content
                break

        if not grab_message:
            await tagged_response(
                ctx, f"Could not find a recent essage from user {user_to_grab}"
            )
            return

        db = self.db_session()

        if (
            db.query(Grab)
            .filter(
                Grab.author_id == str(user_to_grab.id),
                Grab.message == grab_message,
            )
            .count()
            != 0
        ):
            await tagged_response(ctx, "That grab already exists!")
            return
        db.add(
            Grab(
                author_id=str(user_to_grab.id),
                channel=str(ctx.channel.id),
                message=grab_message,
            )
        )
        db.commit()
        db.close()

        await tagged_response(ctx, f"Successfully saved: '*{grab_message}*'")

    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="grabs",
        brief="Returns all grabbed messages of mentioned person",
        description="Returns all grabbed messages of mentioned person from the database.",
        usage="[mentioned-user]",
        help=(
            "\nLimitations: The command will only look for a mentioned user."
            " Any additional plain text, other mentioned users, or @here/@everyone"
            " will be ignored."
        ),
    )
    async def get_grabs(self, ctx):
        if self.invalid_channel(ctx):
            return

        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_grab:
            await tagged_response(ctx, "You must mention a user to get their grabs!")
            return

        if user_to_grab.bot:
            await tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        grabs = (
            db.query(Grab)
            .order_by(desc(Grab.time))
            .filter(Grab.author_id == str(user_to_grab.id))
        )
        if len(list(grabs)) == 0:
            await tagged_response(ctx, f"No grabs found for {user_to_grab.name}")
            return

        embed = SafeEmbed(
            title=f"Grabs for {user_to_grab.name}",
            description=f"Let's take a stroll down memory lane...",
        )
        embed.set_thumbnail(url=user_to_grab.avatar_url)
        embeds = []
        field_counter = 1
        for index, grab_ in enumerate(grabs):
            filtered_message = sub_mentions_for_usernames(ctx.bot, str(grab_.message))
            embed = (
                SafeEmbed(
                    title=f"Grabs for {user_to_grab.name}",
                    description=f"Let's take a stroll down memory lane...",
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f'"{filtered_message}"',
                value=grab_.time.date(),
                inline=False,
            )
            if field_counter == self.config.grabs_max or index == len(list(grabs)) - 1:
                embed.set_thumbnail(url=user_to_grab.avatar_url)
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        db.close()

        await paginate(ctx, embeds=embeds, restrict=True)

    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="grabr",
        brief="Returns a random grabbed message",
        description="Returns a random grabbed message of a random user or of a mentioned user from the database.",
        usage="[mentioned-user/blank]",
        help=(
            "\nLimitations: Any additional plain text, mentioned users, or @here/@everyone"
            " will be ignored."
        ),
    )
    async def random_grab(self, ctx):
        if self.invalid_channel(ctx):
            return

        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_grab:
            await tagged_response(ctx, "You must mention a user to get a random grab!")
            return

        if user_to_grab.bot:
            await tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        if user_to_grab:
            grabs = db.query(Grab).filter(Grab.author_id == str(user_to_grab.id))
        else:
            grabs = db.query(Grab)

        if grabs:
            random_index = randint(0, grabs.count() - 1)
            grab = grabs[random_index]
            filtered_message = sub_mentions_for_usernames(ctx.bot, grab.message)
            embed = SafeEmbed(
                title=f'"{filtered_message}"',
                description=f"{user_to_grab.name}, {grab.time.date()}",
            )
            embed.set_thumbnail(url=user_to_grab.avatar_url)
        else:
            await tagged_response(
                f"No messages found for {user_to_grab or 'this channel'}"
            )
            return

        db.close()

        await tagged_response(ctx, embed=embed)
