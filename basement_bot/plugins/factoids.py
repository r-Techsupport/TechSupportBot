from discord.ext import commands

from database import DatabaseHandler
from sqlalchemy import Column, Integer, String

db_handler = DatabaseHandler()


class Factoid(db_handler.Base):
    __tablename__ = "factoids"

    text = Column(String, primary_key=True)
    message = Column(String)


db_handler.initialize()


def setup(bot):
    bot.add_command(add_factoid)
    bot.add_command(get_factoid)


@commands.command(name="r")
async def add_factoid(ctx, arg1, arg2):
    db = db_handler.Session()
    db.add(Factoid(text=arg1.lower(), message=arg2))
    db.commit()


@commands.command(name="getf")
async def get_factoid(ctx, arg):
    db = db_handler.Session()
    for f in db.query(Factoid).filter(Factoid.text == arg):
        await ctx.send(f.message)
