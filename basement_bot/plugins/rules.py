import base
from discord.ext import commands


def setup(bot):
    class Rule(bot.db.Model):
        __tablename__ = "guildrules"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String)
        number = bot.db.Column(bot.db.Integer)
        description = bot.db.Column(bot.db.String)

    return bot.process_plugin_setup(cogs=[Rules], models=[Rule])


class Rules(base.BaseCog):

    RULE_ICON_URL = "https://cdn.icon-icons.com/icons2/907/PNG/512/balance-scale-of-justice_icon-icons.com_70554.png"

    @commands.group(name="rule")
    async def rule_group(self, ctx):
        pass

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="add",
        brief="Adds a rule",
        description="Adds a rule by number for the current server",
        usage="[number] [description]",
    )
    async def add_rule(self, ctx, number: int, *, description: str):
        # first check if a rule with this number/guild-id exists
        existing_rule = await self.get_rule_by_number(ctx, number)

        if existing_rule:
            await self.bot.tagged_response(ctx, f"Rule {number} already exists")
            return

        rule = await self.models.Rule(
            guild_id=str(ctx.guild.id), number=number, description=description
        ).create()

        await self.bot.tagged_response(ctx, f"Rule {number} added: {description}")

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="delete",
        brief="Deletes a rule",
        description="Deletes a rule by number for the current server",
        usage="[number]",
    )
    async def delete_rule(self, ctx, number: int):
        rule = await self.get_rule_by_number(ctx, number)

        if not rule:
            await self.bot.tagged_response(ctx, "I couldn't find that rule")
            return

        description = rule.description

        await rule.delete()

        await self.bot.tagged_response(ctx, f"Rule {number} deleted: {description}")

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="get",
        brief="Gets a rule",
        description="Gets a rule by number for the current server",
        usage="[number]",
    )
    async def get_rule(self, ctx, number: int):
        rule = await self.get_rule_by_number(ctx, number)

        if not rule:
            await self.bot.tagged_response(ctx, "I couldn't find that rule")
            return

        embed = self.bot.embed_api.Embed(
            title=f"Rule {rule.number}", description=rule.description
        )

        embed.set_thumbnail(url=self.RULE_ICON_URL)

        await self.bot.tagged_response(ctx, embed=embed)

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="all",
        brief="Gets all rules",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self, ctx):
        rules = await self.models.Rule.query.where(
            self.models.Rule.guild_id == str(ctx.guild.id)
        ).gino.all()

        if not rules:
            await self.bot.tagged_response(
                ctx, "I couldn't find any rules for this server"
            )
            return

        embed = self.bot.embed_api.Embed(
            title="Server Rules",
            description="By talking on this server, you agree to the following rules",
        )

        for rule in rules:
            embed.add_field(
                name=f"Rule {rule.number}", value=rule.description, inline=False
            )

        embed.set_thumbnail(url=self.RULE_ICON_URL)

        await ctx.send(embed=embed)

    async def get_rule_by_number(self, ctx, number):
        rule = (
            await self.models.Rule.query.where(
                self.models.Rule.guild_id == str(ctx.guild.id),
            )
            .where(self.models.Rule.number == number)
            .gino.first()
        )
        return rule
