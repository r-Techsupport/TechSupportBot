import cogs
import sqlalchemy
from discord.ext import commands


class Rule(cogs.DatabasePlugin.get_base()):
    __tablename__ = "guildrules"

    pk = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    guild_id = sqlalchemy.Column(sqlalchemy.String)
    number = sqlalchemy.Column(sqlalchemy.Integer)
    description = sqlalchemy.Column(sqlalchemy.String)


def setup(bot):
    bot.add_cog(Rules(bot))


class Rules(cogs.DatabasePlugin):

    HAS_CONFIG = False
    MODEL = Rule

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
        db = self.db_session()

        existing_rule = (
            db.query(Rule)
            .filter(Rule.guild_id == str(ctx.guild.id), Rule.number == number)
            .first()
        )

        if existing_rule:
            await self.tagged_response(ctx, f"Rule {number} already exists")
        else:
            rule = Rule(
                guild_id=str(ctx.guild.id), number=number, description=description
            )

            db.add(rule)
            db.commit()

            await self.tagged_response(ctx, f"Rule {number} added: {description}")

        db.close()

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="delete",
        brief="Deletes a rule",
        description="Deletes a rule by number for the current server",
        usage="[number]",
    )
    async def delete_rule(self, ctx, number: int):
        db = self.db_session()

        rule = (
            db.query(Rule)
            .filter(Rule.guild_id == str(ctx.guild.id), Rule.number == number)
            .first()
        )

        if not rule:
            await self.tagged_response(ctx, "I couldn't find that rule")
        else:
            description = rule.description
            db.delete(rule)
            db.commit()
            await self.tagged_response(ctx, f"Rule {number} deleted: {description}")

        db.close()

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="get",
        brief="Gets a rule",
        description="Gets a rule by number for the current server",
        usage="[number]",
    )
    async def get_rule(self, ctx, number: int):
        db = self.db_session()

        rule = (
            db.query(Rule)
            .filter(Rule.guild_id == str(ctx.guild.id), Rule.number == number)
            .first()
        )

        if rule:
            db.expunge(rule)
        db.close()

        if not rule:
            await self.tagged_response(ctx, "I couldn't find that rule")
            return

        embed = self.bot.embed_api.Embed(
            title=f"Rule {rule.number}", description=rule.description
        )

        embed.set_thumbnail(url=self.RULE_ICON_URL)

        await self.tagged_response(ctx, embed=embed)

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="all",
        brief="Gets all rules",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self, ctx):
        db = self.db_session()

        rules = (
            db.query(Rule)
            .filter(
                Rule.guild_id == str(ctx.guild.id),
            )
            .order_by(Rule.number)
            .all()
        )

        for rule in rules:
            db.expunge(rule)
        db.close()

        if not rules:
            await self.tagged_response(ctx, "I couldn't find any rules for this server")
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
