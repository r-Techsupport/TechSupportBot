import asyncio
import datetime
import functools
import random
from datetime import timedelta

import base
import discord
import embeds
import util
from discord import Color as embed_colors
from discord.ext import commands


async def setup(bot):
    class DuckUser(bot.db.Model):
        __tablename__ = "duckusers"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        author_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        befriend_count = bot.db.Column(bot.db.Integer, default=0)
        kill_count = bot.db.Column(bot.db.Integer, default=0)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.ExtensionConfig()
    config.add(
        key="hunt_channels",
        datatype="list",
        title="DuckHunt Channel IDs",
        description="The IDs of the channels the duck should appear in",
        default=[],
    )
    config.add(
        key="min_wait",
        datatype="int",
        title="Min wait (hours)",
        description="The minimum number of hours to wait between duck events",
        default=2,
    )
    config.add(
        key="max_wait",
        datatype="int",
        title="Max wait (hours)",
        description="The maximum number of hours to wait between duck events",
        default=4,
    )
    config.add(
        key="timeout",
        datatype="int",
        title="Duck timeout (seconds)",
        description="The amount of time before the duck disappears",
        default=60,
    )
    config.add(
        key="cooldown",
        datatype="int",
        title="Duck cooldown (seconds)",
        description="The amount of time to wait between bef/bang messages",
        default=5,
    )
    config.add(
        key="success_rate",
        datatype="int",
        title="Success rate (percent %)",
        description="The success rate of bef/bang messages",
        default=50,
    )

    await bot.add_cog(DuckHunt(bot=bot, models=[DuckUser], extension_name="duck"))
    bot.add_extension_config("duck", config)


class DuckHunt(base.LoopCog):
    DUCK_PIC_URL = "https://cdn.icon-icons.com/icons2/1446/PNG/512/22276duck_98782.png"
    BEFRIEND_URL = "https://cdn.icon-icons.com/icons2/603/PNG/512/heart_love_valentines_relationship_dating_date_icon-icons.com_55985.png"
    KILL_URL = "https://cdn.icon-icons.com/icons2/1919/PNG/512/huntingtarget_122049.png"
    ON_START = False
    CHANNELS_KEY = "hunt_channels"

    async def loop_preconfig(self):
        self.cooldowns = {}

    async def wait(self, config, _):
        await asyncio.sleep(
            random.randint(
                config.extensions.duck.min_wait.value * 3600,
                config.extensions.duck.max_wait.value * 3600,
            )
        )

    async def execute(self, config, guild, channel):
        if not channel:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "warning",
                "Channel not found for Duckhunt loop - continuing",
                send=True,
            )
            return

        self.cooldowns[guild.id] = {}

        start_time = datetime.datetime.now()
        embed = discord.Embed(
            title="*Quack Quack*",
            description="Befriend the duck with `bef` or shoot with `bang`",
        )
        embed.set_image(url=self.DUCK_PIC_URL)
        embed.color = discord.Color.green()

        message = await channel.send(embed=embed)

        response_message = None
        try:
            response_message = await self.bot.wait_for(
                "message",
                timeout=config.extensions.duck.timeout.value,
                # can't pull the config in a non-coroutine
                check=functools.partial(self.message_check, config, channel),
            )
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "error",
                "Exception thrown waiting for duckhunt input",
                exception=e,
            )

        await message.delete()

        if response_message:
            duration = (datetime.datetime.now() - start_time).seconds
            action = (
                "befriended" if response_message.content.lower() == "bef" else "killed"
            )
            await self.handle_winner(
                response_message.author, guild, action, duration, channel
            )
        else:
            await self.got_away(channel)

    async def got_away(self, channel):
        """Sends a "got away!" embed when timeout passes"""
        embed = discord.Embed(
            title="A duck got away!",
            description="Then he waddled away, waddle waddle, 'til the very next day",
        )
        embed.color = discord.Color.red()

        await channel.send(embed=embed)

    async def handle_winner(self, winner, guild, action, duration, channel):
        await self.bot.guild_log(
            guild,
            "logging_channel",
            "info",
            f"Duck {action} by {winner} in #{channel.name}",
            send=True,
        )

        duck_user = await self.get_duck_user(winner.id, guild.id)
        if not duck_user:
            duck_user = self.models.DuckUser(
                author_id=str(winner.id),
                guild_id=str(guild.id),
                befriend_count=0,
                kill_count=0,
            )
            await duck_user.create()

        if action == "befriended":
            await duck_user.update(befriend_count=duck_user.befriend_count + 1).apply()
        else:
            await duck_user.update(kill_count=duck_user.kill_count + 1).apply()

        await duck_user.update(updated=datetime.datetime.now()).apply()

        embed = discord.Embed(
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

        await channel.send(embed=embed)

    def pick_quote(self) -> str:
        QUOTES_FILE = "extensions/duckQuotes.txt"
        with open(QUOTES_FILE, "r") as file:
            lines = file.readlines()
            random_line = random.choice(lines)
            return random_line.strip()

    def message_check(self, config, channel, message):
        # ignore other channels
        if message.channel.id != channel.id:
            return False

        if not message.content.lower() in ["bef", "bang"]:
            return False

        cooldowns = self.cooldowns.get(message.guild.id, {})

        if (
            datetime.datetime.now()
            - cooldowns.get(message.author.id, datetime.datetime.now())
        ).seconds < config.extensions.duck.cooldown.value:
            cooldowns[message.author.id] = datetime.datetime.now()
            asyncio.create_task(
                message.author.send(
                    f"I said to wait {config.extensions.duck.cooldown.value} seconds! Resetting timer..."
                )
            )
            return False

        weights = (
            config.extensions.duck.success_rate.value,
            100 - config.extensions.duck.success_rate.value,
        )

        # Check to see if random failure
        choice_ = random.choice(random.choices([True, False], weights=weights, k=1000))
        if not choice_:
            cooldowns[message.author.id] = datetime.datetime.now()
            quote = self.pick_quote()
            embed = embeds.DenyEmbed(message=quote)
            embed.set_footer(
                text=f"Try again in {config.extensions.duck.cooldown.value} seconds"
            )
            asyncio.create_task(
                message.author.timeout(timedelta(seconds=10), reason="Missed a duck")
            )
            asyncio.create_task(
                message.channel.send(
                    content=message.author.mention,
                    embed=embed,
                )
            )

        return choice_

    async def get_duck_user(self, user_id, guild_id):
        duck_user = (
            await self.models.DuckUser.query.where(
                self.models.DuckUser.author_id == str(user_id)
            )
            .where(self.models.DuckUser.guild_id == str(guild_id))
            .gino.first()
        )

        return duck_user

    @commands.group(
        brief="Executes a duck command",
        description="Executes a duck command",
    )
    async def duck(self, ctx):
        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck stats",
        description="Gets duck friendships and kills for yourself or another user",
        usage="@user (defaults to yourself)",
    )
    async def stats(self, ctx, *, user: discord.Member = None):
        if not user:
            user = ctx.message.author

        if user.bot:
            await ctx.send_deny_embed(
                "If it looks like a duck, quacks like a duck, it's a duck!"
            )
            return

        duck_user = await self.get_duck_user(user.id, ctx.guild.id)
        if not duck_user:
            await ctx.send_deny_embed("That user has not partcipated in the duck hunt")
            return

        embed = discord.Embed(title="Duck Stats", description=user.mention)
        embed.color = embed_colors.green()
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck friendship scores",
        description="Gets duck friendship scores for all users",
    )
    async def friends(self, ctx):
        duck_users = (
            await self.models.DuckUser.query.order_by(
                -self.models.DuckUser.befriend_count
            )
            .where(self.models.DuckUser.befriend_count > 0)
            .where(self.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await ctx.send_deny_embed("It appears nobody has befriended any ducks")
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = (
                discord.Embed(title="Duck Friendships") if field_counter == 1 else embed
            )

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Friends: `{duck_user.befriend_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        ctx.task_paginate(pages=embeds)

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck kill scores",
        description="Gets duck kill scores for all users",
    )
    async def killers(self, ctx):
        duck_users = (
            await self.models.DuckUser.query.order_by(-self.models.DuckUser.kill_count)
            .where(self.models.DuckUser.kill_count > 0)
            .where(self.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await ctx.send_deny_embed("It appears nobody has killed any ducks")
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = discord.Embed(title="Duck Kills") if field_counter == 1 else embed

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Kills: `{duck_user.kill_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        ctx.task_paginate(pages=embeds)

    def get_user_text(self, duck_user):
        user = self.bot.get_user(int(duck_user.author_id))
        if user:
            user_text = f"{user.display_name}"
            user_text_extra = f"({user.name})" if user.name != user.display_name else ""
        else:
            user_text = "<Unknown>"
            user_text_extra = ""
        return f"{user_text}{user_text_extra}"
