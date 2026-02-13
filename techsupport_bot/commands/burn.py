"""
Module for the burn command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Burn plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Burn(bot=bot))


class Burn(cogs.BaseCog):
    """Class for Burn command on the discord bot.

    Attributes:
        PHRASES (list[str]): The list of phrases to pick from
    """

    PHRASES: list[str] = [
        "Sick BURN!",
        "Someone is going to need ointment for that BURN!",
        "Fire! Call 911! Someone just got BURNED!",
        "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOH BURN!",
        "BURN ALERT!",
        "Was that message a hot pan? BECAUSE IT BURNS!",
    ]

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        """Initializes burn command handlers and registers context menu command.

        Args:
            bot (bot.TechSupportBot): The bot instance
        """
        super().__init__(bot=bot)
        self.ctx_menu = app_commands.ContextMenu(
            name="Declare Burn",
            callback=self.burn_from_message,
            extras={"module": "burn"},
        )
        if getattr(self.bot, "tree", None):
            self.bot.tree.add_command(self.ctx_menu)

    async def handle_burn(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User,
        message: discord.Message,
    ) -> None:
        """The core logic to handle burn execution.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member | discord.User): The user that was called in the burn command
            message (discord.Message): The message to react to.
                Will be None if no message could be found
        """
        if not message:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_burn_not_found_message())
            )
            return

        await auxiliary.add_list_of_reactions(
            message=message, reactions=build_burn_reactions()
        )

        phrase_pool = normalize_phrase_pool(self.PHRASES)
        invalid_phrase_message = validate_phrase_pool(phrase_pool)
        if invalid_phrase_message:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(invalid_phrase_message)
            )
            return

        phrase_index = choose_phrase_index(phrase_pool)
        burn_description = build_burn_description(phrase_pool, phrase_index)

        embed = auxiliary.generate_basic_embed(
            title="Burn Alert!",
            description=burn_description,
            color=discord.Color.red(),
        )
        await interaction.followup.send(
            embed=embed, content=auxiliary.construct_mention_string([user])
        )

    async def burn_command(
        self: Self,
        interaction: discord.Interaction,
        user_to_match: discord.Member | discord.User,
    ) -> None:
        """The core logic of the slash burn command.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user_to_match (discord.Member | discord.User): The user in which to burn
        """
        prefix = self.bot.guild_configs[str(interaction.guild.id)].command_prefix

        message = await auxiliary.search_channel_for_message(
            channel=interaction.channel,
            prefix=prefix,
            member_to_match=user_to_match,
        )

        await self.handle_burn(interaction, user_to_match, message)

    @app_commands.command(
        name="burn",
        description="Declares a user's message as a burn",
        extras={"module": "burn"},
    )
    async def burn(
        self: Self, interaction: discord.Interaction, user_to_match: discord.Member
    ) -> None:
        """The slash command entry point for burn.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user_to_match (discord.Member): The user in which to burn
        """
        await interaction.response.defer(ephemeral=False)
        await self.burn_command(interaction, user_to_match)

    async def burn_from_message(
        self: Self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Context menu callback to declare a burn on a selected message.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            message (discord.Message): The selected message for the context menu command
        """
        await interaction.response.defer(ephemeral=False)

        target_author_id = resolve_burn_target_for_context_menu(
            message_author_id=getattr(message.author, "id", 0),
            interaction_user_id=interaction.user.id,
        )
        if target_author_id == interaction.user.id:
            target_user = interaction.user
        else:
            target_user = message.author

        await self.handle_burn(interaction, target_user, message)


def build_burn_reactions() -> list[str]:
    """Builds the ordered list of burn reactions.

    Returns:
        list[str]: The emoji reactions to add to the target message
    """
    reactions = ["🔥", "🚒"]
    reactions.append("👨‍🚒")
    return reactions


def normalize_phrase_pool(phrases: list[str]) -> list[str]:
    """Normalizes and deduplicates burn phrases.

    Args:
        phrases (list[str]): Raw phrases to normalize

    Returns:
        list[str]: A deduplicated list of clean phrases
    """
    normalized_phrases = []
    seen = set()
    for phrase in phrases:
        cleaned_phrase = phrase.strip()
        if len(cleaned_phrase) == 0:
            continue
        if cleaned_phrase in seen:
            continue
        seen.add(cleaned_phrase)
        normalized_phrases.append(cleaned_phrase)

    return normalized_phrases


def validate_phrase_pool(phrases: list[str]) -> str | None:
    """Validates that there are usable phrases to render.

    Args:
        phrases (list[str]): The normalized phrase list

    Returns:
        str | None: A deny message if invalid, otherwise None
    """
    if len(phrases) == 0:
        return "There are no burn phrases configured"

    return None


def choose_phrase_index(phrases: list[str]) -> int:
    """Chooses a random index from a phrase pool.

    Args:
        phrases (list[str]): The available phrase pool

    Raises:
        ValueError: Raised if an empty list is supplied

    Returns:
        int: The index of the chosen phrase
    """
    if len(phrases) == 0:
        raise ValueError("phrase list cannot be empty")

    return random.randint(0, len(phrases) - 1)


def build_burn_description(phrases: list[str], chosen_index: int) -> str:
    """Builds the burn embed description from phrase data.

    Args:
        phrases (list[str]): The available phrase pool
        chosen_index (int): The index selected by the phrase chooser

    Returns:
        str: A formatted burn phrase description
    """
    phrase = phrases[chosen_index]
    return f"🔥🔥🔥 {phrase} 🔥🔥🔥"


def build_burn_not_found_message() -> str:
    """Builds the deny message for missing target messages.

    Returns:
        str: A user-facing deny message
    """
    return "I could not find a message to reply to"


def resolve_burn_target_for_context_menu(
    message_author_id: int, interaction_user_id: int
) -> int:
    """Resolves the target user id for context menu burn calls.

    Args:
        message_author_id (int): The selected message author id
        interaction_user_id (int): The user id of the command invoker

    Returns:
        int: The chosen target user id
    """
    if message_author_id <= 0:
        return interaction_user_id

    return message_author_id
