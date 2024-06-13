"""
Commands that manage, start, and interact with the voting system
The cog in the file is named:
    Voting

This file contains 1 commands:
    /voting
"""

from __future__ import annotations

import datetime
from datetime import timedelta
from typing import TYPE_CHECKING, Self

import aiocron
import discord
import munch
import ui
import ui.persistent_voting
from core import cogs, extensionconfig
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the Voting cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="votes_channel_id",
        datatype="str",
        title="Votes channel",
        description="The forum channel id as a string to start votes in",
        default="",
    )
    config.add(
        key="ping_role_id",
        datatype="str",
        title="The role to ping when starting a vote",
        description=(
            "The role to ping when starting a vote, which will always be pinged"
        ),
        default="",
    )
    await bot.add_cog(Voting(bot=bot, extension_name="voting"))
    bot.add_extension_config("voting", config)


class Voting(cogs.LoopCog):
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

        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.voting.votes_channel_id.value)
        )
        roles = await interaction.guild.fetch_roles()
        role = next(
            role
            for role in roles
            if role.id == int(config.extensions.voting.ping_role_id.value)
        )

        vote = await self.bot.models.Votes(
            guild_id=str(interaction.guild.id),
            message_id="0",
            vote_owner_id=str(interaction.user.id),
            vote_description=form.vote_reason.value,
            anonymous=anonymous,
            blind=blind,
        ).create()

        embed = await self.build_vote_embed(vote.vote_id, interaction.guild)
        view = ui.VotingButtonPersistent()

        vote_thread, vote_message = await channel.create_thread(
            name=f"VOTE: {form.vote_short}",
            allowed_mentions=discord.AllowedMentions(roles=True),
            embed=embed,
            content=role.mention,
            view=view,
        )

        await interaction.followup.send(
            f"Your vote has been started, {vote_thread.mention}", ephemeral=True
        )

        await vote.update(message_id=str(vote_message.id)).apply()

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
        self, vote_id: int, guild: discord.Guild
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
        owner = await guild.fetch_member(int(db_entry.vote_owner_id))
        exact_time = int((db_entry.start_time + timedelta(hours=72)).timestamp())
        rounted_time = (exact_time - (exact_time % 3600)) + 3600
        embed = discord.Embed(
            title="Vote",
            description=f"{db_entry.vote_description}",
        )
        embed.add_field(
            name="Vote information",
            value=(
                f"Vote owner: {owner.mention}\n"
                "This vote will run until: "
                f"<t:{rounted_time}:f>\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Votes",
            value=await self.make_fancy_voting_list(
                guild,
                db_entry.vote_ids_yes.split(","),
                db_entry.vote_ids_no.split(","),
                (db_entry.vote_active and hide) or db_entry.anonymous,
            ),
        )
        print_yes_votes = "?" if (hide and db_entry.vote_active) else db_entry.votes_yes
        print_no_votes = "?" if (hide and db_entry.vote_active) else db_entry.votes_no
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

        embed = await self.build_vote_embed(db_entry.vote_id, interaction.guild)
        await interaction.message.edit(embed=embed, view=view)
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

        embed = await self.build_vote_embed(db_entry.vote_id, interaction.guild)
        await interaction.message.edit(embed=embed, view=view)
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

        embed = await self.build_vote_embed(db_entry.vote_id, interaction.guild)
        await interaction.message.edit(embed=embed, view=view)
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

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """Makes a check every hour for if any votes have concluded

        Args:
            config (munch.Munch): The guild config where the vote was started
        """
        # We check every hour on the hour for completed votes
        await aiocron.crontab("0 * * * *").next()

    async def execute(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
        """This looks for completed votes and ends then

        Args:
            config (munch.Munch): The guild config for the guild with the vote
            guild (discord.Guild): The guild the vote is being run in
        """
        active_votes = (
            await self.bot.models.Votes.query.where(
                self.bot.models.Votes.vote_active == True
            )
            .where(self.bot.models.Votes.guild_id == str(guild.id))
            .gino.all()
        )
        for vote in active_votes:
            end_time = int((vote.start_time + timedelta(hours=72)).timestamp())
            if end_time <= int(datetime.datetime.utcnow().timestamp()):
                await self.end_vote(vote, guild)

    async def end_vote(self, vote: munch.Munch, guild: discord.Guild) -> None:
        """This ends a vote, and if it was anonymous purges who voted for what from the database
        This will edit the vote message and remove the buttons, and mention the vote owner

        Args:
            vote (munch.Munch): The vote database object that needs to be ended
            guild (discord.Guild): The guild that vote belongs to
        """
        await vote.update(vote_active=False).apply()
        embed = await self.build_vote_embed(vote.vote_id, guild)
        # If the vote is anonymous, at this point we need to clear the vote record forever
        if vote.anonymous:
            await vote.update(vote_ids_yes="", vote_ids_no="").apply()
        # Placeholder till config sets a voting channel
        config = self.bot.guild_configs[str(guild.id)]
        channel = await guild.fetch_channel(
            config.extensions.voting.votes_channel_id.value
        )
        message = await channel.fetch_message(int(vote.message_id))
        vote_owner = await guild.fetch_member(int(vote.vote_owner_id))
        await message.edit(content="Vote over", embed=embed, view=None)
        await channel.send(
            f"{vote_owner.mention} your vote is over. Results:", embed=embed
        )
