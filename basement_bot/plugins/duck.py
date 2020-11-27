import asyncio
import datetime
from random import randint

from cogs import DatabasePlugin, LoopPlugin
from discord import Embed
from sqlalchemy import Column, DateTime, Integer, String


class DuckUser(DatabasePlugin.BaseTable):
    __tablename__ = "duckusers"

    author_id = Column(String, primary_key=True)
    befriend_count = Column(Integer, default=0)
    kill_count = Column(Integer, default=0)
    updated = Column(DateTime, default=datetime.datetime.utcnow)


def setup(bot):
    bot.add_cog(DuckHunt(bot))


class DuckHunt(DatabasePlugin, LoopPlugin):

    PLUGIN_NAME = __name__
    MODEL = DuckUser
    DUCK_PIC_URL = "https://cdn.icon-icons.com/icons2/1446/PNG/512/22276duck_98782.png"

    async def loop_preconfig(self):
        self.waiting = True

        min_wait = self.config.min_hours
        max_wait = self.config.max_hours

        if min_wait < 0 or max_wait < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if max_wait - min_wait <= 0:
            raise RuntimeError(f"Max time must be greater than min time")

        self.channel = self.bot.get_channel(self.config.channel)
        if not self.channel:
            raise RuntimeError("Unable to get channel for DuckHunt plugin")

        if not self.config.on_start:
            await self.wait()

    async def execute(self):
        self.waiting = False

        start_time = datetime.datetime.now()
        embed = Embed(
            title="*Quack Quack*",
            description="Befriend the duck with `bef` or kill with `bang`!",
        )
        embed.set_image(url=self.DUCK_PIC_URL)
        message = await self.channel.send(embed=embed)

        response_message = None
        try:
            response_message = await self.bot.wait_for(
                "message",
                timeout=self.config.timeout_seconds,
                check=lambda m: m.content in ["bef", "bang"],
            )
        except Exception as e:
            pass

        await message.delete()
        self.waiting = True

        if response_message:
            duration = (datetime.datetime.now() - start_time).seconds
            action = "befriended" if response_message.content == "bef" else "killed"
            await self.handle_winner(response_message.author, action, duration)

    async def handle_winner(self, winner, action, duration):
        db = self.db_session()

        new_user = False
        duck_user = (
            db.query(DuckUser).filter(DuckUser.author_id == str(winner.id)).first()
        )
        if not duck_user:
            new_user = True
            duck_user = DuckUser(
                author_id=str(winner.id), befriend_count=0, kill_count=0
            )

        if action == "befriended":
            duck_user.befriend_count += 1
        else:
            duck_user.kill_count += 1

        duck_user.updated = datetime.datetime.now()

        if new_user:
            db.add(duck_user)

        db.commit()

        embed = Embed(
            title=f"Duck {action}!",
            description=f"{winner.mention} {action} the duck in {duration} seconds!",
        )
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await self.channel.send(embed=embed)

    async def wait(self):
        await asyncio.sleep(
            randint(
                self.config.min_hours*3600,
                self.config.max_hours*3600,
            )
        )
