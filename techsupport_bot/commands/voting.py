"""This holds a command to manually adjust someones nickname
Uses the same filter as the automatic nickname filter"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import ui
import ui.persistent_voting
from core import auxiliary, cogs
from discord import app_commands
from functions import nickname

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the nicknamefixer cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(Voting(bot=bot))


class Voting(cogs.BaseCog):
    """The class that holds the nickname fixer"""

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command(
        name="voting",
        description="Voting",
        extras={
            "module": "voting",
        },
    )
    async def votingbutton(self: Self, interaction: discord.Interaction) -> None:
        """Manually adjusts someones nickname to comply with the nickname filter
        Does not send a DM

        Args:
            interaction (discord.Interaction): The interaction the command was called at
        """

        form = ui.VoteCreation()
        await interaction.response.send_modal(form)
        await form.wait()

        message = await interaction.followup.send(f"{form.vote_reason.value}")

        vote = await self.bot.models.Votes(
            guild_id=str(interaction.guild.id),
            message_id=str(message.id),
            vote_owner_id=str(interaction.user.id),
            vote_description=form.vote_reason.value,
        ).create()

        embed = await self.build_vote_embed(vote.vote_id)
        view = ui.PersistentView(test="AAAAAAAAAAAAAA")

        await message.edit(
            content=f"{form.vote_reason.value}",
            embed=embed,
            view=view,
        )

        print(message.id)

    async def search_db_for_vote_by_id(self, vote_id: int):
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.vote_id == vote_id
        ).gino.first()

    async def search_db_for_vote_by_message(self, message_id: str):
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.message_id == message_id
        ).gino.first()

    async def build_vote_embed(self, vote_id: int):
        db_entry = await self.search_db_for_vote_by_id(vote_id)
        embed = discord.Embed(title="Vote", description=db_entry.vote_description)
        embed.add_field(name="Votes", value=db_entry.vote_ids_yes)
        embed.add_field(
            name="Vote counts",
            value=f"Votes for yes: {db_entry.votes_yes}\nVotes for no: {db_entry.votes_no}",
        )
        embed.set_footer(text=f"Vote ID: {db_entry.vote_id}")
        return embed

    async def register_vote(
        self,
        voter: discord.Member,
        view: discord.ui.View,
        message: discord.Message,
    ):
        db_entry = await self.search_db_for_vote_by_message(str(message.id))
        await db_entry.update(vote_ids_yes=str(voter.id), votes_yes=1).apply()
        embed = await self.build_vote_embed(db_entry.vote_id)
        await message.edit(content=db_entry.vote_description, embed=embed, view=view)
