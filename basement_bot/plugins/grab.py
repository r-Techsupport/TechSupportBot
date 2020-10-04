import datetime
from random import randint

from discord import Embed
from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String

from cogs import DatabasePlugin
from utils.helpers import priv_response, tagged_response


class Grab(DatabasePlugin.BaseTable):
    __tablename__ = "grabs"

    pk = Column(Integer, primary_key=True)
    author_id = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)


def setup(bot):
    bot.add_cog(Grabber(bot, Grab))


class Grabber(DatabasePlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 20

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
        channel = str(ctx.message.channel.id)
        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_grab:
            await priv_response(ctx, "You must tag a user to grab!")
            return

        if user_to_grab.bot:
            await priv_response(ctx, "Ain't gonna catch me slipping!")
            return

        grab_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab and not message.content.startswith(
                f"{self.bot.config.main.required.command_prefix}grab"
            ):
                grab_message = message.content
                break

        if not grab_message:
            await priv_response(
                ctx, f"Could not find a recent essage from user {user_to_grab}"
            )
            return

        db = self.db_session()

        try:
            if (
                db.query(Grab)
                .filter(
                    Grab.author_id == str(user_to_grab.id),
                    Grab.message == grab_message,
                )
                .count()
                != 0
            ):
                await priv_response(ctx, "That grab already exists!")
                return
            db.add(
                Grab(
                    author_id=str(user_to_grab.id),
                    channel=channel,
                    message=grab_message,
                )
            )
            db.commit()
            await priv_response(ctx, f"Successfully saved: '*{grab_message}*'")
        except Exception:
            await priv_response(ctx, "I had an issue remembering that message!")

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
        channel = str(ctx.message.channel.id)
        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if not user_to_grab:
            await priv_response(ctx, "You must tag a user to grab!")
            return

        if user_to_grab.bot:
            await priv_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        try:
            grabs = db.query(Grab).filter(Grab.author_id == str(user_to_grab.id))
            embed = Embed(
                title=f"Grabs for {user_to_grab.name}",
                description=f"Let's take a stroll down memory lane...",
            )
            embed.set_thumbnail(url=user_to_grab.avatar_url)
            if grabs:
                for index, grab_ in enumerate(grabs):
                    embed.add_field(
                        name=f'"{grab_.message}"', value=grab_.time.date(), inline=False
                    )
                    if index == 20:
                        break
            else:
                embed.add_field(name=None, value="No grabs found!")
            await tagged_response(ctx, embed=embed)
        except Exception as e:
            await tagged_response(ctx, e)

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
        channel = str(ctx.message.channel.id)
        user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

        if user_to_grab and user_to_grab.bot:
            await priv_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        try:
            if user_to_grab:
                grabs = db.query(Grab).filter(Grab.author_id == str(user_to_grab.id))
            else:
                grabs = db.query(Grab)

            if grabs:
                random_index = randint(0, grabs.count() - 1)
                grab = grabs[random_index]
                embed = Embed(
                    title=f'"{grab.message}"',
                    description=f"{user_to_grab.name}, {grab.time.date()}",
                )
                embed.set_thumbnail(url=user_to_grab.avatar_url)
            else:
                await priv_response(
                    f"No messages found for {user_to_grab or 'this channel'}"
                )
                return

            await tagged_response(ctx, embed=embed)
        except Exception:
            return
