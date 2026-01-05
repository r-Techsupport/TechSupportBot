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
from core import auxiliary, cogs, extensionconfig
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
        key="votes_channel_roles",
        datatype="dict[str, list[str]]",
        title="Votes channels → allowed roles",
        description=(
            "Map of forum channel IDs to a list of role IDs. "
            "User must have at least one role from the list."
        ),
        default={},
    )
    config.add(
        key="active_role_id",
        datatype="str",
        title="Active voter role",
        description="User must have this role to start or participate in votes",
        default="",
    )
    await bot.add_cog(Voting(bot=bot, extension_name="voting"))
    bot.add_extension_config("voting", config)


class Voting(cogs.LoopCog):
    """The class that holds the core voting system"""

    VOTE_CONFIG = {
        "yes": {
            "ids_field": "vote_ids_yes",
            "count_field": "votes_yes",
            "already_msg": "You have already voted yes",
            "success_msg": "Your vote for yes has been counted",
        },
        "no": {
            "ids_field": "vote_ids_no",
            "count_field": "votes_no",
            "already_msg": "You have already voted no",
            "success_msg": "Your vote for no has been counted",
        },
        "abstain": {
            "ids_field": "vote_ids_abstain",
            "count_field": "votes_abstain",
            "already_msg": "You have already voted to abstain",
            "success_msg": "Your vote to abstain has been counted",
        },
    }

    @app_commands.command(
        name="vote",
        description="Starts a yes/no vote that runs for 72 hours",
        extras={
            "module": "voting",
        },
    )
    async def votingbutton(
        self: Self,
        interaction: discord.Interaction,
        channel: str,
        blind: bool = False,
        anonymous: bool = True,
    ) -> None:
        """Will open a modal

        Args:
            interaction (discord.Interaction): The interaction the command was called at
            blind (bool): A blind vote hides the tally and who voted for what
                for the duration of the vote
            anonymous (bool): A blind vote hides the tally for the duration of the vote
                This also hides who voted for what forever, and triggers it to be deleted
                from the database upon completion of the vote
        """
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(int(channel))

        if not self.user_can_use_vote_channel(
            member=interaction.user,
            channel=channel,
            config=config,
        ):
            embed = auxiliary.prepare_deny_embed(
                "You do not have rights to start that vote!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        form = ui.VoteCreation()
        await interaction.response.send_modal(form)
        await form.wait()

        # Fetch all roles from the guild
        roles = await interaction.guild.fetch_roles()

        # Get the allowed role IDs for this channel from the config
        channel_role_map: dict[str, list[str]] = (
            config.extensions.voting.votes_channel_roles.value
        )
        allowed_role_ids = channel_role_map.get(str(channel.id), [])

        # Build a list of discord.Role objects
        ping_roles: list[discord.Role] = [
            role for role in roles if str(role.id) in allowed_role_ids
        ]

        # Build the mention string
        roles_to_ping = " ".join(role.mention for role in ping_roles)

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
            content=roles_to_ping,
            view=view,
        )

        await interaction.followup.send(
            f"Your vote has been started, {vote_thread.mention}", ephemeral=True
        )

        await vote.update(
            thread_id=str(vote_thread.id), message_id=str(vote_message.id)
        ).apply()

    @votingbutton.autocomplete("channel")
    async def vote_channel_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not config:
            return []

        member = interaction.user
        if not isinstance(member, discord.Member):
            return []

        channel_role_map = config.extensions.voting.votes_channel_roles.value

        choices: list[app_commands.Choice[str]] = []

        for channel_id in channel_role_map.keys():
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                continue

            if not self.user_can_use_vote_channel(
                member=member,
                channel=channel,
                config=config,
                name_filter=current,
            ):
                continue

            choices.append(
                app_commands.Choice(
                    name=f"#{channel.name}",
                    value=str(channel.id),
                )
            )

            if len(choices) >= 25:
                break

        return choices

    def user_can_use_vote_channel(
        self: Self,
        *,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
        config,
        name_filter: str | None = None,
    ) -> bool:
        """
        Returns True if the user is allowed to use this channel for voting.

        Conditions:
        - User has active_role_id
        - Channel exists
        - Channel is a ForumChannel
        - User has at least one role mapped to the channel
        - Channel name matches name_filter (if provided)
        """
        if not isinstance(channel, discord.ForumChannel):
            return False

        voting_config = config.extensions.voting

        active_role_id: str = voting_config.active_role_id.value
        channel_role_map: dict[str, list[str]] = voting_config.votes_channel_roles.value

        # Channel must be configured
        allowed_role_ids = channel_role_map.get(str(channel.id))
        if not allowed_role_ids:
            return False

        user_role_ids = {str(role.id) for role in member.roles}

        # Must have the active role
        if active_role_id not in user_role_ids:
            return False

        # Must have at least one channel-specific role
        if not user_role_ids.intersection(allowed_role_ids):
            return False

        # Optional name filter (autocomplete)
        if name_filter and name_filter.lower() not in channel.name.lower():
            return False

        return True

    async def search_db_for_vote_by_id(self: Self, vote_id: int) -> munch.Munch:
        """Gets a vote entry from the database by a given vote ID

        Args:
            vote_id (int): The vote ID (primary key) to search for

        Returns:
            munch.Munch: The database entry that matches the ID
        """
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.vote_id == vote_id
        ).gino.first()

    async def search_db_for_vote_by_message(self: Self, message_id: str) -> munch.Munch:
        """Gets a vote entry from the database by a given message ID

        Args:
            message_id (str): The message ID to search for

        Returns:
            munch.Munch: The database entry that matches the ID
        """
        return await self.bot.models.Votes.query.where(
            self.bot.models.Votes.message_id == message_id
        ).gino.first()

    async def build_vote_embed(
        self: Self, vote_id: int, guild: discord.Guild
    ) -> discord.Embed:
        """Builds the embed that shows information about the vote

        Args:
            vote_id (int): The ID of the vote to build the embed for
            guild (discord.Guild): The guild the vote belongs to. Needed to look up membership

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
                db_entry.vote_ids_abstain.split(","),
                (db_entry.vote_active and hide) or db_entry.anonymous,
            ),
        )
        print_yes_votes = "?" if (hide and db_entry.vote_active) else db_entry.votes_yes
        print_no_votes = "?" if (hide and db_entry.vote_active) else db_entry.votes_no
        print_abstain_votes = (
            "?" if (hide and db_entry.vote_active) else db_entry.votes_abstain
        )
        embed.add_field(
            name="Vote counts",
            value=(
                f"Votes for yes: {print_yes_votes}\n"
                f"Votes for no: {print_no_votes}\n"
                f"Votes to abstain: {print_abstain_votes}"
            ),
        )
        footer_str = f"Vote ID: {db_entry.vote_id}. "
        if db_entry.blind:
            footer_str += "This vote is blind. "
        if db_entry.anonymous:
            footer_str += "This vote is anonymous. "
        embed.set_footer(text=footer_str)
        return embed

    async def make_fancy_voting_list(
        self: Self,
        guild: discord.Guild,
        voters_yes: list[str],
        voters_no: list[str],
        voters_abstain: list[str],
        should_hide: bool,
    ) -> str:
        """This makes a new line seperated string to be used in the "Votes" field
        in the displayed vote embed

        Args:
            guild (discord.Guild): The guild this vote is taking place in
            voters_yes (list[str]): The list of IDs of yes votes
            voters_no (list[str]): The list of IDs of no votes
            voters_abstain (list[str]): The list of IDs of abstian votes
            should_hide (bool): Should who voted for what be hidden

        Returns:
            str: The prepared string, that respects blind/anonymous
        """
        voters = voters_yes + voters_no + voters_abstain
        final_str = []
        for user in voters:
            if len(user) == 0:
                continue
            user_object = await guild.fetch_member(int(user))
            if should_hide:
                final_str.append(f"{user_object.display_name} - ?")
            elif user in voters_yes:
                final_str.append(f"{user_object.display_name} - yes")
            elif user in voters_no:
                final_str.append(f"{user_object.display_name} - no")
            else:
                final_str.append(f"{user_object.display_name} - abstain")
        final_str.sort()
        return "\n".join(final_str)

    async def register_vote(
        self: Self,
        interaction: discord.Interaction,
        view: discord.ui.View,
        vote_type: str,  # "yes" | "no" | "abstain"
    ) -> None:
        config = self.VOTE_CONFIG[vote_type]
        user_id = str(interaction.user.id)

        db_entry = await self.search_db_for_vote_by_message(str(interaction.message.id))

        # Get the correct vote_ids field dynamically
        vote_ids = getattr(db_entry, config["ids_field"]).split(",")

        if user_id in vote_ids:
            await interaction.response.send_message(
                config["already_msg"], ephemeral=True
            )
            return

        # Remove user from any previous vote
        db_entry = self.clear_vote_record(db_entry, user_id)

        # Add vote
        vote_ids.append(user_id)
        setattr(db_entry, config["ids_field"], ",".join(vote_ids))

        # Increment counter
        setattr(
            db_entry,
            config["count_field"],
            getattr(db_entry, config["count_field"]) + 1,
        )

        # Update vote_ids_all
        vote_ids_all = db_entry.vote_ids_all.split(",")
        vote_ids_all.append(user_id)
        db_entry.vote_ids_all = ",".join(vote_ids_all)

        await db_entry.update(
            vote_ids_no=db_entry.vote_ids_no,
            votes_no=db_entry.votes_no,
            vote_ids_yes=db_entry.vote_ids_yes,
            votes_yes=db_entry.votes_yes,
            vote_ids_abstain=db_entry.vote_ids_abstain,
            votes_abstain=db_entry.votes_abstain,
            vote_ids_all=db_entry.vote_ids_all,
        ).apply()

        embed = await self.build_vote_embed(db_entry.vote_id, interaction.guild)
        await interaction.message.edit(embed=embed, view=view)

        await interaction.response.send_message(config["success_msg"], ephemeral=True)

    async def clear_vote(
        self: Self,
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
            vote_ids_abstain=db_entry.vote_ids_abstain,
            votes_abstain=db_entry.votes_abstain,
            vote_ids_all=db_entry.vote_ids_all,
        ).apply()

        embed = await self.build_vote_embed(db_entry.vote_id, interaction.guild)
        await interaction.message.edit(embed=embed, view=view)
        await interaction.response.send_message(
            "Your vote has been removed", ephemeral=True
        )

    def clear_vote_record(
        self: Self, db_entry: munch.Munch, user_id: str
    ) -> munch.Munch:
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

        # If there is a vote for abstain, remote it
        vote_ids_abstain = db_entry.vote_ids_abstain.split(",")
        if user_id in vote_ids_abstain:
            vote_ids_abstain.remove(user_id)
            db_entry.votes_abstain -= 1
        db_entry.vote_ids_abstain = ",".join(vote_ids_abstain)

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
        # pylint: disable=C0121
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

    async def end_vote(self: Self, vote: munch.Munch, guild: discord.Guild) -> None:
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
            await vote.update(
                vote_ids_yes="", vote_ids_no="", vote_ids_abstain=""
            ).apply()

        channel = await guild.fetch_channel(int(vote.thread_id))
        message = await channel.fetch_message(int(vote.message_id))
        vote_owner = await guild.fetch_member(int(vote.vote_owner_id))
        await message.edit(content="Vote over", embed=embed, view=None)
        await channel.send(
            f"{vote_owner.mention} your vote is over. Results:", embed=embed
        )
