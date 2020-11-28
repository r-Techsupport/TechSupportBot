import asyncio
import datetime
from random import choice, choices

from cogs import DatabasePlugin, LoopPlugin
from discord import Color as embed_colors
from discord import Embed
from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String
from utils.helpers import *


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
    BEFRIEND_URL = "https://cdn.icon-icons.com/icons2/603/PNG/512/heart_love_valentines_relationship_dating_date_icon-icons.com_55985.png"
    KILL_URL = "https://cdn.icon-icons.com/icons2/1919/PNG/512/huntingtarget_122049.png"
    UNITS = "seconds"

    async def loop_preconfig(self):
        self.cooldowns = {}

        if self.config.success_percent > 100 or self.config.success_percent < 0:
            self.config.success_percent = 80

        self.channel = self.bot.get_channel(self.config.channel)
        if not self.channel:
            raise RuntimeError("Unable to get channel for DuckHunt plugin")

        self.setup_random_waiting("min_hours", "max_hours")

    def message_check(self, message):
        # ignore other channels
        if message.channel.id != self.channel.id:
            return False

        if not message.content.lower() in ["bef", "bang"]:
            return False

        if self.cooldowns.get(message.author.id):
            if (
                datetime.datetime.now() - self.cooldowns.get(message.author.id)
            ).seconds < self.config.cooldown_seconds:
                return False

        weights = (self.config.success_percent, 100 - self.config.success_percent)
        choice_ = choice(choices([True, False], cum_weights=weights, k=2))
        if not choice_:
            self.cooldowns[message.author.id] = datetime.datetime.now()

            failure_message = (
                "failed to befriend the duck!"
                if message.content == "bef"
                else "failed to kill the duck!"
            )
            self.bot.loop.create_task(
                self.channel.send(
                    f"{message.author.mention} {failure_message} Try again in {self.config.cooldown_seconds} seconds"
                )
            )

        return choice_

    async def execute(self):
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
                check=self.message_check,
            )
        except Exception as e:
            pass

        await message.delete()

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
        embed.color = (
            embed_colors.blurple() if action == "befriended" else embed_colors.red()
        )
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(
            url=self.BEFRIEND_URL if action == "befriended" else self.KILL_URL
        )

        await self.channel.send(embed=embed)

    @commands.command(
        name="duck_stats",
        brief="Get duck stats",
        description="Gets duck friendships and kills for yourself or another user",
        usage="@user (defaults to yourself)",
        help="",
    )
    async def stats(self, ctx, *args):
        query_user = (
            ctx.message.mentions[0] if ctx.message.mentions else ctx.message.author
        )

        if query_user.bot:
            await priv_response(
                ctx, "If it looks like a duck, quacks like a duck, it's a duck!"
            )
            return

        db = self.db_session()
        duck_user = (
            db.query(DuckUser).filter(DuckUser.author_id == str(query_user.id)).first()
        )
        if not duck_user:
            await priv_response(ctx, "That user has not partcipated in the duck hunt")
            return

        embed = Embed(title="Duck Stats", description=query_user.mention)
        embed.color = embed_colors.green()
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await tagged_response(ctx, embed=embed)

    @commands.command(
        name="duck_friends",
        brief="Get duck friendship scores",
        description="Gets duck friendship scores for all users",
        usage="",
        help="",
    )
    async def friends(self, ctx):
        db = self.db_session()
        duck_users = db.query(DuckUser).order_by(DuckUser.befriend_count.desc()).all()
        if len(list(duck_users)) == 0:
            await priv_response(
                ctx, "Nobody appears to be participating in the Duck Hunt"
            )
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = Embed(title="Duck Friendships") if field_counter == 1 else embed

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Friends: `{duck_user.befriend_count}`",
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await paginate(ctx, embeds=embeds, restrict=True)

    @commands.command(
        name="duck_killers",
        brief="Get duck kill scores",
        description="Gets duck kill scores for all users",
        usage="",
        help="",
    )
    async def killers(self, ctx):
        db = self.db_session()
        duck_users = db.query(DuckUser).order_by(DuckUser.kill_count.desc()).all()
        if len(list(duck_users)) == 0:
            await priv_response(
                ctx, "Nobody appears to be participating in the Duck Hunt"
            )
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = Embed(title="Duck Kills") if field_counter == 1 else embed

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Kills: `{duck_user.kill_count}`",
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await paginate(ctx, embeds=embeds, restrict=True)

    def get_user_text(self, duck_user):
        user = self.bot.get_user(int(duck_user.author_id))
        if user:
            user_text = f"{user.display_name}"
            user_text_extra = f"({user.name})" if user.name != user.display_name else ""
        else:
            user_text = "<Unknown>"
            user_text_extra = ""
        return f"{user_text}{user_text_extra}"
