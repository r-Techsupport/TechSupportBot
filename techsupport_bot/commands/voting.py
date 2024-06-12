"""This holds a command to manually adjust someones nickname
Uses the same filter as the automatic nickname filter"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Self

import discord
import munch
import ui
import ui.persistent_voting
from core import cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the Voting cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(Voting(bot=bot))


class Voting(cogs.BaseCog):
    """The class that holds the core voting system"""

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command(
        name="voting",
        description="Starts a yes/no vote that runs for 72 hours",
        extras={
            "module": "voting",
        },
    )
    async def votingbutton(
        self: Self,
        interaction: discord.Interaction,
        blind: bool = False,
        anonymous: bool = False,
    ) -> None:
        """Will open a modal

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
            anonymous=anonymous,
            blind=blind,
        ).create()

        embed = await self.build_vote_embed(vote.vote_id, interaction)
        view = ui.PersistentView()

        await message.edit(
            content=f"{form.vote_reason.value}",
            embed=embed,
            view=view,
        )

    async def search_db_for_vote_by_id(self, vote_id: int):
        """Gets a vote entry from the database by a given vote ID

        Args:
            vote_id (int): The vote ID (primary key) to search for

        Returns:
            munch.Munch: The database entry that matches the ID
        """
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.vote_id == vote_id
        ).gino.first()

    async def search_db_for_vote_by_message(self, message_id: str) -> munch.Munch:
        """Gets a vote entry from the database by a given message ID

        Args:
            vote_id (int): The message ID to search for

        Returns:
            munch.Munch: The database entry that matches the ID
        """
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.message_id == message_id
        ).gino.first()

    async def build_vote_embed(
        self, vote_id: int, interaction: discord.Interaction
    ) -> discord.Embed:
        """Builds the embed that shows information about the vote

        Args:
            vote_id (int): The ID of the vote to build the embed for
            interaction (discord.Interaction): The interaction that called for an update to the embed

        Returns:
            discord.Embed: The fully built embed ready to be sent
        """
        db_entry = await self.search_db_for_vote_by_id(vote_id)
        hide = db_entry.blind or db_entry.anonymous
        owner = await interaction.guild.fetch_member(int(db_entry.vote_owner_id))
        embed = discord.Embed(
            title="Vote",
            description=f"{db_entry.vote_description}",
        )
        embed.add_field(
            name="Vote information",
            value=(
                f"Vote owner: {owner.mention}\n"
                "This vote will run until: "
                f"<t:{int((db_entry.start_time + timedelta(hours=72)).timestamp())}:f>\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Votes",
            value=await self.make_fancy_voting_list(
                interaction.guild,
                db_entry.vote_ids_yes.split(","),
                db_entry.vote_ids_no.split(","),
                hide,
            ),
        )
        print_yes_votes = "?" if hide else db_entry.votes_yes
        print_no_votes = "?" if hide else db_entry.votes_no
        embed.add_field(
            name="Vote counts",
            value=f"Votes for yes: {print_yes_votes}\nVotes for no: {print_no_votes}",
        )
        footer_str = f"Vote ID: {db_entry.vote_id}. "
        if db_entry.blind:
            footer_str += "This vote is blind. "
        if db_entry.anonymous:
            footer_str += "This vote is anonymous. "
        embed.set_footer(text=footer_str)
        return embed

    async def make_fancy_voting_list(
        self,
        guild: discord.Guild,
        voters_yes: list[str],
        voters_no: list[str],
        should_hide: bool,
    ) -> str:
        """This makes a new line seperated string to be used in the "Votes" field
        in the displayed vote embed

        Args:
            guild (discord.Guild): The guild this vote is taking place in
            voters_yes (list[str]): The list of IDs of yes votes
            voters_no (list[str]): The list of IDs of no votes
            should_hide (bool): Should who voted for what be hidden

        Returns:
            str: The prepared string, that respects blind/anonymous
        """
        voters = voters_yes + voters_no
        final_str = []
        for user in voters:
            if len(user) == 0:
                continue
            user_object = await guild.fetch_member(int(user))
            if should_hide:
                final_str.append(f"{user_object.display_name} - ?")
            elif user in voters_yes:
                final_str.append(f"{user_object.display_name} - yes")
            else:
                final_str.append(f"{user_object.display_name} - no")
        final_str.sort()
        return "\n".join(final_str)

    async def register_yes_vote(
        self,
        interaction: discord.Interaction,
        view: discord.ui.View,
    ) -> None:
        """This updates the vote database when someone votes yes

        Args:
            interaction (discord.Interaction): The interaction that started the vote
            view (discord.ui.View): The view that was interacted with
        """
        db_entry = await self.search_db_for_vote_by_message(str(interaction.message.id))

        # Update vote_ids_yes
        vote_ids_yes = db_entry.vote_ids_yes.split(",")
        if str(interaction.user.id) in vote_ids_yes:
            await interaction.response.send_message(
                "You have already voted yes", ephemeral=True
            )
            return  # Already voted yes, don't do anything more

        db_entry = self.clear_vote_record(db_entry, str(interaction.user.id))

        vote_ids_yes.append(str(interaction.user.id))
        db_entry.vote_ids_yes = ",".join(vote_ids_yes)

        # Increment votes_yes
        db_entry.votes_yes += 1

        # Update vote_ids_all
        vote_ids_all = db_entry.vote_ids_all.split(",")
        vote_ids_all.append(str(interaction.user.id))
        db_entry.vote_ids_all = ",".join(vote_ids_all)

        await db_entry.update(
            vote_ids_no=db_entry.vote_ids_no,
            votes_no=db_entry.votes_no,
            vote_ids_yes=db_entry.vote_ids_yes,
            votes_yes=db_entry.votes_yes,
            vote_ids_all=db_entry.vote_ids_all,
        ).apply()

        embed = await self.build_vote_embed(db_entry.vote_id, interaction)
        await interaction.message.edit(
            content=db_entry.vote_description, embed=embed, view=view
        )
        await interaction.response.send_message(
            "Your vote for yes has been counted", ephemeral=True
        )

    async def register_no_vote(
        self,
        interaction: discord.Interaction,
        view: discord.ui.View,
    ) -> None:
        """This updates the vote database when someone votes no

        Args:
            interaction (discord.Interaction): The interaction that started the vote
            view (discord.ui.View): The view that was interacted with
        """
        db_entry = await self.search_db_for_vote_by_message(str(interaction.message.id))

        # Update vote_ids_no
        vote_ids_no = db_entry.vote_ids_no.split(",")
        if str(interaction.user.id) in vote_ids_no:
            await interaction.response.send_message(
                "You have already voted no", ephemeral=True
            )
            return  # Already voted no, don't do anything more

        db_entry = self.clear_vote_record(db_entry, str(interaction.user.id))

        vote_ids_no.append(str(interaction.user.id))
        db_entry.vote_ids_no = ",".join(vote_ids_no)

        # Increment votes_no
        db_entry.votes_no += 1

        # Update vote_ids_all
        vote_ids_all = db_entry.vote_ids_all.split(",")
        vote_ids_all.append(str(interaction.user.id))
        db_entry.vote_ids_all = ",".join(vote_ids_all)

        await db_entry.update(
            vote_ids_no=db_entry.vote_ids_no,
            votes_no=db_entry.votes_no,
            vote_ids_yes=db_entry.vote_ids_yes,
            votes_yes=db_entry.votes_yes,
            vote_ids_all=db_entry.vote_ids_all,
        ).apply()

        embed = await self.build_vote_embed(db_entry.vote_id, interaction)
        await interaction.message.edit(
            content=db_entry.vote_description, embed=embed, view=view
        )
        await interaction.response.send_message(
            "Your vote for no has been counted", ephemeral=True
        )

    async def clear_vote(
        self,
        interaction: discord.Interaction,
        view: discord.ui.View,
    ) -> None:
        """This updates the vote database when someone wishes to remove their vote

        Args:
            interaction (discord.Interaction): The interaction that started the vote
            view (discord.ui.View): The view that was interacted with
        """
        db_entry = await self.search_db_for_vote_by_message(str(interaction.message.id))

        db_entry = self.clear_vote_record(db_entry, str(interaction.user.id))

        await db_entry.update(
            vote_ids_no=db_entry.vote_ids_no,
            votes_no=db_entry.votes_no,
            vote_ids_yes=db_entry.vote_ids_yes,
            votes_yes=db_entry.votes_yes,
            vote_ids_all=db_entry.vote_ids_all,
        ).apply()

        embed = await self.build_vote_embed(db_entry.vote_id, interaction)
        await interaction.message.edit(
            content=db_entry.vote_description, embed=embed, view=view
        )
        await interaction.response.send_message(
            "Your vote has been removed", ephemeral=True
        )

    def clear_vote_record(self, db_entry: munch.Munch, user_id: str) -> munch.Munch:
        """Clears the vote from a person from the database
        Should always be called before changing or adding a vote

        Args:
            db_entry (munch.Munch): The database entry of the vote
            user_id (str): The user ID who is voting

        Returns:
            munch.Munch: The updated database entry that has NOT been synced to postgres
        """
        # If there is a vote for yes, remove it
        vote_ids_yes = db_entry.vote_ids_yes.split(",")
        if user_id in vote_ids_yes:
            vote_ids_yes.remove(user_id)
            db_entry.votes_yes -= 1
        db_entry.vote_ids_yes = ",".join(vote_ids_yes)

        # If there is a vote for no, remote it
        vote_ids_no = db_entry.vote_ids_no.split(",")
        if user_id in vote_ids_no:
            vote_ids_no.remove(user_id)
            db_entry.votes_no -= 1
        db_entry.vote_ids_no = ",".join(vote_ids_no)

        # Remove from vote id all
        vote_ids_all = db_entry.vote_ids_all.split(",")
        if user_id in vote_ids_all:
            vote_ids_all.remove(user_id)
        db_entry.vote_ids_all = ",".join(vote_ids_all)

        return db_entry
