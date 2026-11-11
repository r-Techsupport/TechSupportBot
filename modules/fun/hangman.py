"""Module for the hangman extension for the bot."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
import ui
from core import auxiliary, cogs
from modules.moderation import featureban

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the HangMan plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(HangmanCog(bot=bot))


class HangmanGame:
    """
    A class that represents a game of Hangman.

    The game includes the logic for tracking the word to be guessed, the guesses made,
    and the state of the hangman figure based on incorrect guesses. It also supports
    additional functionality such as adding more guesses and determining whether the game
    is finished or failed.

    Attributes:
        HANG_PICS (list[str]): The list of hangman pictures.
        word (str): The word that players need to guess.
        guesses (set): A set of guessed letters.
        step (int): The current number of incorrect guesses made.
        max_guesses (int): The maximum number of incorrect guesses allowed before the game ends.
        started (datetime): The UTC timestamp of when the game was started.
        id (UUID): A unique identifier for the game.
        finished (bool): Determines if the game has been finished or not
        failed (bool): Determines if the players failed to guess the word

    Args:
        word (str): The word for the game. It must be an alphabetic string without underscores.
        max_guesses (int, optional): The maximum number of incorrect guesses allowed.

    Raises:
        ValueError: A valid alphabetic word wasn't provided.
    """

    HANG_PICS: list[str] = [
        """
        +---+
        |   |
            |
            |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
            |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
        |   |
            |
            |
        =========""",
        r"""
        +---+
        |   |
        O   |
       /|   |
            |
            |
        =========""",
        r"""
        +---+
        |   |
        O   |
       /|\  |
            |
            |
        =========""",
        r"""
        +---+
        |   |
        O   |
       /|\  |
       /    |
            |
        =========""",
        r"""
        +---+
        |   |
        O   |
       /|\  |
       / \  |
            |
        =========""",
    ]

    def __init__(self: Self, word: str, max_guesses: int = 6) -> None:
        if not word or "_" in word or not word.isalpha():
            raise ValueError("valid word must be provided")
        self.word = word
        self.guesses = set()
        self.step = 0
        self.max_guesses = max_guesses
        self.started = datetime.datetime.utcnow()
        self.id = uuid.uuid4()

    def draw_word_state(self: Self) -> str:
        """Makes a string with blank spaces and guessed letters

        Returns:
            str: The formatted string ready to be printed in the embed
        """
        state = ""
        for letter in self.word:
            value = letter if letter.lower() in self.guesses else "_"
            state += f" {value} "

        return state

    def draw_hang_state(self: Self) -> str:
        """Gets the pre-programmed string for the hangman state
        Based on how many guesses and how close the man is to hanging

        Returns:
            str: The str representation of the correct picture
        """
        picture_index = min(
            len(self.HANG_PICS) - 1,  # Maximum valid index
            int(self.step / self.max_guesses * (len(self.HANG_PICS) - 1)),
        )
        return self.HANG_PICS[picture_index]

    def guess(self: Self, letter: str) -> bool:
        """Registers a guess to the given game

        Args:
            letter (str): The single letter to guess

        Raises:
            ValueError: Raised if letter isn't a single character
            RuntimeError: Raised if the game is finished

        Returns:
            bool: True if the letter is in the game, false if it isn't
        """
        found = True
        if len(letter) > 1:
            raise ValueError("guess must be letter")
        if self.finished:
            raise RuntimeError("this game is finished")
        if not letter.lower() in self.word.lower():
            found = False
            self.step += 1
        self.guesses.add(letter.lower())

        return found

    @property
    def finished(self: Self) -> bool:
        """
        Determines if the game of Hangman is finished.

        The game is considered finished if:
        - The number of incorrect guesses (`step`) is greater than or
            equal to the maximum allowed (`max_guesses`).
        - All letters in the word have been correctly guessed, meaning the game has been won.

        Returns:
            bool: True if the game is finished (either won or lost), False otherwise.
        """
        if self.step < 0 or self.step >= self.max_guesses:
            return True
        if all(letter in self.guesses for letter in self.word):
            return True
        return False

    @property
    def failed(self: Self) -> bool:
        """
        Determines if the game was unsuccessful.

        The game is considered a failure when the number of incorrect guesses (`step`)
        equals or exceeds the maximum allowed guesses (`max_guesses`), meaning the players
        failed to guess the word within the allowed attempts.

        Returns:
            bool: True if the game was unsuccessful (i.e., the number of incorrect guesses
                is greater than or equal to the maximum allowed), False otherwise.
        """
        if self.step >= self.max_guesses:
            return True
        return False

    def guessed(self: Self, letter: str) -> bool:
        """
        Method to know if a letter has already been guessed

        Args:
            letter (str): The letter to check if it has been guessed

        Raises:
            ValueError: Raised if the letter isn't a single character

        Returns:
            bool: True if it's been guessed, False if it hasn't
        """

        if len(letter) > 1:
            raise ValueError("guess must be letter")
        if letter.lower() in self.guesses:
            return True
        return False

    def remaining_guesses(self: Self) -> int:
        """
        Calculates the number of guesses remaining in the game.

        The remaining guesses are determined by subtracting the number of incorrect
        guesses (`step`) from the maximum allowed guesses (`max_guesses`).

        Returns:
            int: The number of guesses the players have left.
        """
        return self.max_guesses - self.step

    def add_guesses(self: Self, num_guesses: int) -> None:
        """
        Increases the total number of allowed guesses in the game.

        Args:
            num_guesses (int): The number of additional guesses to add to the
                current maximum allowed guesses.
        """
        self.max_guesses += num_guesses


async def can_stop_game(interaction: discord.Interaction) -> bool:
    """
    Checks if a user has the ability to stop the running game

    Args:
        interaction (discord.Interaction): The context in which the stop command was run

    Raises:
        AttributeError: The Hangman game could not be found
        AppCommandError: No admin roles have been defined in the config
        MissingAnyRole: The doesn't have the admin roles needed to stop the game

    Returns:
        bool: True the user can stop the game, False they cannot
    """
    cog = interaction.client.get_cog("HangmanCog")
    if not cog:
        raise AttributeError("could not find hangman cog when checking game states")

    game_data = cog.games.get(interaction.channel.id)
    if not game_data:
        return True

    user = game_data.get("user")
    if getattr(user, "id", 0) == interaction.user.id:
        return True

    roles = []
    for role_name in configuration.get_config_entry(
        interaction.guild.id, "hangman_hangman_roles"
    ):
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            continue
        roles.append(role)

    if not roles:
        raise app_commands.AppCommandError("no hangman admin roles found")

    if not any(role in interaction.user.roles for role in roles):
        raise app_commands.MissingAnyRole(roles)

    return True


class HangmanCog(cogs.BaseCog):
    """Class to define the Hangman game.

    Args:
        bot (bot.TechSupportBot): The bot instance that this cog is a part of.

    Attributes:
        games (dict): A dictionary to store ongoing games, where the keys are
                      player identifiers and the values are the current game state.
        hangman_app_group (app_commands.Group): The command group for the Hangman extension.
    """

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        super().__init__(bot)
        self.games = {}

    hangman_app_group: app_commands.Group = app_commands.Group(
        name="hangman",
        description="Command Group for the Hangman Extension",
        guild_only=True,
    )

    async def check_if_banned(self: Self, member: discord.Member) -> bool:
        """Check whether the member is banned from Hangman in this guild.

        Args:
            member (discord.Member): The member to check

        Returns:
            bool: Whether the member is banned from Hangman
        """
        return await featureban.is_feature_banned(
            member.guild.id, member.id, featureban.FeatureFlag.HANGMAN
        )

    async def interaction_check(self: Self, interaction: discord.Interaction) -> bool:
        """Check feature bans before running a Hangman command.

        Args:
            interaction (discord.Interaction): The command interaction

        Raises:
            CheckFailure: The user is banned from Hangman

        Returns:
            bool: Whether the command can run
        """
        if await self.check_if_banned(interaction.user):
            raise app_commands.CheckFailure("You are banned from Hangman.")
        return True

    @hangman_app_group.command(
        name="start",
        description="Start a Hangman game in the current channel.",
        extras={"suppress_logs": True, "ephemeral_error": True},
    )
    async def start_game(
        self: Self, interaction: discord.Interaction, word: str
    ) -> None:
        """Slash command to start a hangman game.

        Args:
            interaction (discord.Interaction): The interaction object from Discord.
            word (str): The word to start the Hangman game with.
        """
        if len(word) > 84:
            await interaction.response.send_message(
                "Your word cannot be more than 85 characters.", ephemeral=True
            )
            return

        try:
            game = HangmanGame(word=word.lower())
        except ValueError as exc:
            await interaction.response.send_message(
                f"Invalid word: {exc}", ephemeral=True
            )
            return

        view = None
        game_data = self.games.get(interaction.channel_id)
        if game_data:
            if game_data["user"].id != interaction.user.id:
                await interaction.response.send_message(
                    "A game is already in progress for this channel.", ephemeral=True
                )
                return

            view = ui.Confirm()
            await view.send(
                interaction=interaction,
                message="There is a current game in progress. Do you want to replace it?",
                ephemeral=True,
            )
            await view.wait()
            if view.value is not ui.ConfirmResponse.CONFIRMED:
                await view.message.edit(
                    embed=auxiliary.prepare_deny_embed(
                        "The current game was not ended."
                    ),
                )
                return

            if self.games.get(interaction.channel_id) is not game_data:
                await view.message.edit(
                    embed=auxiliary.prepare_deny_embed(
                        "The game changed while you were confirming. Please try again."
                    ),
                )
                return
        else:
            await interaction.response.defer(ephemeral=True)

        embed = await self.generate_game_embed(interaction, game, interaction.user)
        message = await interaction.channel.send(embed=embed)
        self.games[interaction.channel_id] = {
            "user": interaction.user,
            "game": game,
            "message": message,
            "last_guesser": None,
        }

        embed = auxiliary.prepare_confirm_embed(
            f"The Hangman game has started with the word: `{word}`"
        )
        if view:
            await view.message.edit(embed=embed)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @hangman_app_group.command(
        name="guess",
        description="Guesses a letter for the current hangman game",
        extras={"ephemeral_error": True},
    )
    async def guess(self: Self, interaction: discord.Interaction, letter: str) -> None:
        """Discord command to guess a letter in a running hangman game

        Args:
            interaction (discord.Interaction): The context in which the command was run in
            letter (str): The letter the user is trying to guess
        """
        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                ),
                ephemeral=True,
            )
            return

        if interaction.user == game_data.get("user"):
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "You cannot guess letters because you started this game!"
                ),
                ephemeral=True,
            )
            return

        if len(letter) > 1 or not letter.isalpha():
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed("You can only guess a letter"),
                ephemeral=True,
            )
            return

        game = game_data.get("game")
        if game.guessed(letter):
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "That letter has already been guessed"
                ),
                ephemeral=True,
            )
            return

        correct = game.guess(letter)
        embed = await self.generate_game_embed(interaction, game, game_data.get("user"))
        message = game_data.get("message")
        await message.edit(embed=embed)

        content = f"Found `{letter}`" if correct else f"Letter `{letter}` not in word"
        if game.finished:
            content = f"{content} - game finished! The word was {game.word}"
            del self.games[interaction.channel.id]
        await interaction.response.send_message(content=content)

    async def generate_game_embed(
        self: Self,
        interaction: discord.Interaction,
        game: HangmanGame,
        owner: discord.Member,
    ) -> discord.Embed:
        """
        Generates an embed representing the current state of the Hangman game.

        Args:
            interaction (discord.Interaction):
                The context or interaction used to generate the embed, which provides
                information about the user and the message.
            game (HangmanGame): The current instance of the Hangman game, used to
                retrieve game state, including word state, remaining guesses, and the
                hangman drawing.
            owner (discord.Member): The owner of the game

        Returns:
            discord.Embed: An embed displaying the current game state, including
                the hangman drawing, word state, remaining guesses, guessed letters,
                and the footer indicating the game status and creator.
        """
        hangman_drawing = game.draw_hang_state()
        hangman_word = game.draw_word_state()
        guess_command = f"</hangman guess:{interaction.data['id']}>"
        embed = discord.Embed(
            title=f"`{hangman_word}`",
            description=f"Use {guess_command} to guess a letter.\n\n```{hangman_drawing}```",
        )

        if game.failed:
            embed.color = discord.Color.red()
            footer_text = f"Game over! The word was `{game.word}`!"
        elif game.finished:
            embed.color = discord.Color.green()
            footer_text = "Word guessed! Nice job!"
        else:
            embed.color = discord.Color.gold()
            embed.add_field(
                name=f"Remaining Guesses {str(game.remaining_guesses())}",
                value="\u200b",
                inline=False,
            )
            embed.add_field(
                name="Guessed Letters",
                value=", ".join(game.guesses) or "None",
                inline=False,
            )

            footer_text = f"Game started by {owner}"

        embed.set_footer(text=footer_text)
        return embed

    @hangman_app_group.command(
        name="redraw",
        description="Redraws the current hangman game",
        extras={"ephemeral_error": True},
    )
    async def redraw(self: Self, interaction: discord.Interaction) -> None:
        """A discord command to make a new embed with a new drawing of the running hangman game
        This redraws the hangman game being played in the current channel

        Args:
            interaction (discord.Interaction): The context in which the command was in
        """
        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        old_message = game_data.get("message")
        try:
            await old_message.delete()
        except discord.errors.NotFound:
            pass

        embed = await self.generate_game_embed(
            interaction, game_data.get("game"), game_data.get("user")
        )
        new_message = await interaction.followup.send(embed=embed, wait=True)
        game_data["message"] = new_message

    @app_commands.check(can_stop_game)
    @hangman_app_group.command(
        name="stop",
        description="Stops the current channel game",
        extras={"ephemeral_error": True},
    )
    async def stop(self: Self, interaction: discord.Interaction) -> None:
        """Checks if a user can stop the hangman game in the current channel
        If they can, the game is stopped

        Args:
            interaction (discord.Interaction): The context in which the command was run in
        """
        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                ),
                ephemeral=True,
            )
            return

        view = ui.Confirm()
        await view.send(
            interaction=interaction,
            message="Are you sure you want to end the current game?",
            ephemeral=True,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await view.message.edit(
                embed=auxiliary.prepare_deny_embed("The current game was not ended"),
            )
            return

        if self.games.get(interaction.channel.id) is not game_data:
            await view.message.edit(
                embed=auxiliary.prepare_deny_embed(
                    "The game changed while you were confirming. Please try again."
                ),
            )
            return

        game = game_data.get("game")
        word = getattr(game, "word", "???")

        del self.games[interaction.channel.id]
        await view.message.edit(
            embed=auxiliary.prepare_confirm_embed(
                "The game in this channel has been ended."
            )
        )
        await interaction.channel.send(
            embed=auxiliary.prepare_confirm_embed(
                f"This game is now finished. The word was: `{word}`"
            )
        )

    @hangman_app_group.command(
        name="add_guesses",
        description="Allows the creator of the game to give more guesses",
        extras={"ephemeral_error": True},
    )
    async def add_guesses(
        self: Self, interaction: discord.Interaction, number_of_guesses: int
    ) -> None:
        """Discord command to allow the game creator to add more guesses.

        Args:
            interaction (discord.Interaction): The context in which the command was run.
            number_of_guesses (int): The number of guesses to add.
        """
        if number_of_guesses <= 0:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "The number of guesses must be a positive integer."
                ),
                ephemeral=True,
            )
            return

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                ),
                ephemeral=True,
            )
            return

        # Ensure only the creator of the game can add guesses
        game_author = game_data.get("user")
        if interaction.user.id != game_author.id:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "Only the creator of the game can add more guesses."
                ),
                ephemeral=True,
            )
            return

        game = game_data.get("game")

        # Add the new guesses
        game.add_guesses(number_of_guesses)

        # Notify the channel
        await interaction.response.send_message(
            content=(
                f"{number_of_guesses} guesses have been added! "
                f"Total guesses remaining: {game.remaining_guesses()}"
            )
        )

        # Update the game embed
        embed = await self.generate_game_embed(interaction, game, game_data.get("user"))
        message = game_data.get("message")
        await message.edit(embed=embed)
