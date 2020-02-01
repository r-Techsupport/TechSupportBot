import datetime

from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String

from utils.database import DatabaseHandler
from utils.helpers import tagged_response

db_handler = DatabaseHandler()

SEARCH_LIMIT = 50


class Grab(db_handler.Base):
    __tablename__ = "grabs"

    pk = Column(Integer, primary_key=True)
    author_id = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)


db_handler.create_all()


def setup(bot):
    bot.add_command(grab)


@commands.command(name="grab")
async def grab(ctx):
    user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

    if not user_to_grab:
        await tagged_response(ctx, "You must tag a user to grab!")
        return

    if user_to_grab.bot:
        await tagged_response(ctx, "Ain't gonna catch me slipping!")
        return

    grab_message = None
    async for message in ctx.channel.history(limit=SEARCH_LIMIT):
        if message.author == user_to_grab and not message.content.startswith("."):
            grab_message = message.content
            break

    if not grab_message:
        await tagged_response(
            ctx, f"Could not find a recent essage from user {user_to_grab}"
        )

    db = db_handler.Session()

    try:
        db.add(Grab(author_id=str(user_to_grab.id), message=grab_message))
        db.commit()
        await tagged_response(ctx, f"Successfully saved: {grab_message}")
    except Exception:
        await tagged_response(ctx, "I had an issue remembering that message!")
