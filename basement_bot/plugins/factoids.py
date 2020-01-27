from discord.ext import commands
from sqlalchemy import Column, Integer, String

from utils.cogs import MatchPlugin
from utils.database import DatabaseHandler
from utils.helpers import get_env_value, tagged_response

FACTOID_PREFIX = get_env_value("FACTOID_PREFIX")

db_handler = DatabaseHandler()


class Factoid(db_handler.Base):
    __tablename__ = "factoids"

    text = Column(String, primary_key=True)
    message = Column(String)


db_handler.initialize()


def setup(bot):
    bot.add_command(add_factoid)
    bot.add_cog(FactoidMatch(bot))
    bot.add_command(delete_factoid)


@commands.command(name="r")
async def add_factoid(ctx, arg1, *args):
    if not args:
        await tagged_response(ctx, "Factoids must not be blank!")
        return

    db = db_handler.Session()

    try:
        # first check if key already exists
        entry = db.query(Factoid).filter(Factoid.text == arg1).first()
        if entry:
            # delete old one
            db.delete(entry)
            await tagged_response(ctx, "Deleting previous entry of factoid trigger...")

        # finally, add new entry
        db.add(Factoid(text=arg1.lower(), message=" ".join(args)))
        db.commit()
        await tagged_response(ctx, f"Successfully added factoid trigger: *{arg1}*")

    except Exception:
        await tagged_response(
            ctx, "I ran into an issue handling your factoid addition..."
        )


@commands.command(name="f")
async def delete_factoid(ctx, arg):
    db = db_handler.Session()

    try:
        entry = db.query(Factoid).filter(Factoid.text == arg).first()
        if entry:
            db.delete(entry)
            db.commit()
        await tagged_response(ctx, f"Successfully deleted factoid trigger: *{arg}*")

    except Exception:
        await tagged_response(
            ctx, "I ran into an issue handling your factoid deletion..."
        )


class FactoidMatch(MatchPlugin):
    def match(self, content):
        return bool(content.startswith(FACTOID_PREFIX))

    async def response(self, ctx, arg):
        db = db_handler.Session()

        try:
            entry = db.query(Factoid).filter(Factoid.text == arg[1:]).first()
            if entry:
                await tagged_response(ctx, entry.message)

        except Exception:
            await tagged_response("I ran into an issue grabbing your factoid...")
