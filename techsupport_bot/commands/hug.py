"""Module for the hug extension for the bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Hug plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Hugger(bot=bot))


def is_valid_hug_target(author_id: int, target_id: int) -> bool:
    """Checks whether a hug target is valid for the invoking user.

    Args:
        author_id (int): The ID of the user sending the hug
        target_id (int): The ID of the target user

    Returns:
        bool: True if the hug can proceed, False otherwise
    """
    return author_id != target_id


def normalize_hug_templates(templates: list[str]) -> list[str]:
    """Normalizes hug templates by trimming and removing empty items.

    Args:
        templates (list[str]): Raw hug phrase templates

    Returns:
        list[str]: Cleaned and usable templates
    """
    normalized_templates = []
    for template in templates:
        normalized_template = template.strip()
        if len(normalized_template) == 0:
            continue
        normalized_templates.append(normalized_template)
    return normalized_templates


def pick_hug_template(templates: list[str]) -> str | None:
    """Picks a hug template from a normalized template list.

    Args:
        templates (list[str]): Normalized hug templates

    Returns:
        str | None: Picked template if available, otherwise None
    """
    if len(templates) == 0:
        return None
    return random.choice(templates)


def build_hug_phrase(template: str, author_mention: str, target_mention: str) -> str:
    """Builds the final hug phrase from a template and mentions.

    Args:
        template (str): The selected hug template
        author_mention (str): Mention string of the user giving the hug
        target_mention (str): Mention string of the user receiving the hug

    Returns:
        str: The fully formatted hug phrase
    """
    return template.format(
        user_giving_hug=author_mention,
        user_to_hug=target_mention,
    )


def build_hug_failure_message() -> str:
    """Builds the deny message for invalid hug actions.

    Returns:
        str: A user-facing deny message
    """
    return "Let's be serious"


def build_hug_embed_data(hug_text: str) -> dict[str, str]:
    """Builds display data used to generate a hug embed.

    Args:
        hug_text (str): The generated hug phrase

    Returns:
        dict[str, str]: Embed title and description values
    """
    return {"title": "You've been hugged!", "description": hug_text}


class Hugger(cogs.BaseCog):
    """Class to make the hug command.

    Attributes:
        HUGS_SELECTION (list[str]): The list of hug phrases to display
        ICON_URL (str): The icon to use when hugging

    Args:
        bot (bot.TechSupportBot): The bot instance

    """

    HUGS_SELECTION: list[str] = [
        "{user_giving_hug} hugs {user_to_hug} forever and ever and ever",
        "{user_giving_hug} wraps arms around {user_to_hug} and clings forever",
        "{user_giving_hug} hugs {user_to_hug} and gives their hair a sniff",
        "{user_giving_hug} glomps {user_to_hug}",
        (
            "cant stop, wont stop. {user_giving_hug} hugs {user_to_hug} until the sun"
            " goes cold"
        ),
        "{user_giving_hug} reluctantly hugs {user_to_hug}...",
        "{user_giving_hug} hugs {user_to_hug} into a coma",
        "{user_giving_hug} smothers {user_to_hug} with a loving hug",
        "{user_giving_hug} squeezes {user_to_hug} to death",
        "{user_giving_hug} swaddles {user_to_hug} like a baby",
        "{user_giving_hug} tackles {user_to_hug} to the ground with a giant glomp",
        "{user_giving_hug} hugs {user_to_hug} and gives them Eskimo kisses",
        (
            "{user_giving_hug} grabs {user_to_hug}, pulls them close,"
            " giving them three hearty raps on the back"
        ),
        "{user_giving_hug} hugs {user_to_hug} and rubs their back slowly",
        "{user_giving_hug} pulls {user_to_hug} into a tight hug and squeezes the sadness out",
        "{user_giving_hug} hugs {user_to_hug} too tightly until they pass out",
        "{user_giving_hug} went to hug {user_to_hug} but missed and ran into the wall instead",
    ]
    ICON_URL: str = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/"
        + "a5/Noto_Emoji_Oreo_1f917.svg/768px-Noto_Emoji_Oreo_1f917.svg.png"
    )

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        super().__init__(bot=bot)
        self.user_context_menu = app_commands.ContextMenu(
            name="Hug User",
            callback=self.hug_user_context,
            extras={"module": "hug"},
        )
        if getattr(self.bot, "tree", None):
            self.bot.tree.add_command(self.user_context_menu)

    @app_commands.command(
        name="hug",
        description="Hugs a mentioned user using an embed",
        extras={"module": "hug"},
    )
    async def hug(
        self: Self, interaction: discord.Interaction, user_to_hug: discord.Member
    ) -> None:
        """Slash command to hug another user.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user_to_hug (discord.Member): The user to hug
        """
        await self.hug_command_base(interaction, user_to_hug)

    async def hug_user_context(
        self: Self, interaction: discord.Interaction, user_to_hug: discord.Member
    ) -> None:
        """User context menu entry point for hugging.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user_to_hug (discord.Member): The user to hug
        """
        await self.hug_command_base(interaction, user_to_hug)

    async def hug_command_base(
        self: Self, interaction: discord.Interaction, user_to_hug: discord.Member
    ) -> None:
        """Shared processor for slash and context-menu hug commands.

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            user_to_hug (discord.Member): The user to hug
        """
        if not is_valid_hug_target(interaction.user.id, user_to_hug.id):
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(build_hug_failure_message()),
                ephemeral=True,
            )
            return

        templates = normalize_hug_templates(self.HUGS_SELECTION)
        template = pick_hug_template(templates)
        if not template:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(build_hug_failure_message()),
                ephemeral=True,
            )
            return

        hug_text = build_hug_phrase(
            template=template,
            author_mention=interaction.user.mention,
            target_mention=user_to_hug.mention,
        )
        embed_data = build_hug_embed_data(hug_text)

        embed = auxiliary.generate_basic_embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=discord.Color.blurple(),
            url=self.ICON_URL,
        )

        await interaction.response.send_message(
            embed=embed, content=auxiliary.construct_mention_string([user_to_hug])
        )
