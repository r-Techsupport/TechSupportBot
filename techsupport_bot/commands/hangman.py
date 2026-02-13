"""Module for the hangman extension for the bot."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Self

import discord
import ui
from core import auxiliary, cogs, extensionconfig
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


MAX_START_WORD_LENGTH = 84


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the HangMan plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="hangman_roles",
        datatype="list",
        title="Hangman admin roles",
        description="The list of role names able to control hangman games",
        default=[],
    )

    await bot.add_cog(HangmanCog(bot=bot))
    bot.add_extension_config("hangman", config)


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


def normalize_secret_word(word: str) -> str:
    """Normalizes a word used for new game creation.

    Args:
        word (str): The raw word supplied by a user

    Returns:
        str: The normalized lower-case word without surrounding whitespace
    """
    return word.strip().lower()


def validate_start_word_input(
    word: str, max_length: int = MAX_START_WORD_LENGTH
) -> str | None:
    """Checks a start word for length and alphabetical requirements.

    Args:
        word (str): The potential secret word for a new game
        max_length (int, optional): The max allowed word length. Defaults to 84.

    Returns:
        str | None: A deny reason if invalid, otherwise None
    """
    normalized_word = normalize_secret_word(word)

    if len(normalized_word) == 0:
        return "A word must be provided"

    if len(normalized_word) > max_length:
        return f"The word must be {max_length} characters or fewer"

    if not normalized_word.isalpha() or "_" in normalized_word:
        return "The word can only contain letters"

    return None


def validate_letter_guess_input(letter: str) -> str | None:
    """Validates a single-letter guess.

    Args:
        letter (str): The guessed letter

    Returns:
        str | None: A deny reason if invalid, otherwise None
    """
    normalized_letter = letter.strip()

    if len(normalized_letter) != 1:
        return "You can only guess a single letter"

    if not normalized_letter.isalpha():
        return "You can only guess alphabetic letters"

    return None


def validate_solve_guess_input(
    word: str, max_length: int = MAX_START_WORD_LENGTH
) -> str | None:
    """Validates a full-word solve guess.

    Args:
        word (str): The proposed full-word answer
        max_length (int, optional): The max allowed guess length. Defaults to 84.

    Returns:
        str | None: A deny reason if invalid, otherwise None
    """
    normalized_word = normalize_secret_word(word)

    if len(normalized_word) == 0:
        return "A word must be provided"

    if len(normalized_word) > max_length:
        return f"The guessed word must be {max_length} characters or fewer"

    if not normalized_word.isalpha():
        return "The guessed word can only contain letters"

    return None


def decide_start_conflict(caller_id: int, owner_id: int) -> str:
    """Determines what action should happen when a game already exists.

    Args:
        caller_id (int): The user id of the command caller
        owner_id (int): The user id of the existing game owner

    Returns:
        str: "confirm-overwrite" when caller is owner, otherwise "deny"
    """
    if caller_id == owner_id:
        return "confirm-overwrite"

    return "deny"


def evaluate_solve_attempt(secret_word: str, guess_word: str) -> bool:
    """Evaluates whether a full-word solve attempt is correct.

    Args:
        secret_word (str): The secret game word
        guess_word (str): The user submitted guess

    Returns:
        bool: True when the guess matches the secret word, otherwise False
    """
    normalized_secret = normalize_secret_word(secret_word)
    normalized_guess = normalize_secret_word(guess_word)
    return normalized_secret == normalized_guess


def build_letter_guess_result(letter: str, correct: bool) -> str:
    """Builds a user-facing result message for a single-letter guess.

    Args:
        letter (str): The guessed letter
        correct (bool): Whether the guess was found in the word

    Returns:
        str: The status message for the guess
    """
    normalized_letter = letter.strip().lower()
    if correct:
        return f"Found `{normalized_letter}`"

    return f"Letter `{normalized_letter}` not in word"


def build_solve_result(guess_word: str, correct: bool) -> str:
    """Builds a user-facing result message for a full-word solve guess.

    Args:
        guess_word (str): The guessed word
        correct (bool): Whether the full-word guess is correct

    Returns:
        str: The status message for the guess
    """
    normalized_word = normalize_secret_word(guess_word)
    if correct:
        return f"`{normalized_word}` is correct"

    return f"`{normalized_word}` is not the word"


def build_add_guesses_result(number_of_guesses: int, remaining_guesses: int) -> str:
    """Builds a user-facing result message for adding more guesses.

    Args:
        number_of_guesses (int): Number of guesses that were added
        remaining_guesses (int): Remaining guesses after update

    Returns:
        str: A formatted status message
    """
    return (
        f"{number_of_guesses} guesses have been added! "
        f"Total guesses remaining: {remaining_guesses}"
    )


def build_stop_permission_denial(
    caller_id: int,
    owner_id: int | None,
    configured_role_names: list[str],
    caller_role_names: list[str],
) -> str | None:
    """Determines if a non-owner is allowed to stop a running game.

    Args:
        caller_id (int): The user id of the command caller
        owner_id (int | None): The owner id for the active game
        configured_role_names (list[str]): Role names from hangman config
        caller_role_names (list[str]): Role names that caller currently has

    Returns:
        str | None: Deny reason if caller cannot stop the game, otherwise None
    """
    if owner_id is not None and caller_id == owner_id:
        return None

    filtered_config_roles = {
        name.strip().lower() for name in configured_role_names if len(name.strip()) > 0
    }
    if len(filtered_config_roles) == 0:
        return "No hangman admin roles are configured"

    normalized_user_roles = {
        name.strip().lower() for name in caller_role_names if len(name.strip()) > 0
    }

    if filtered_config_roles.isdisjoint(normalized_user_roles):
        return "You are not allowed to stop this game"

    return None


def build_game_display_data(
    game: HangmanGame, owner: discord.Member
) -> dict[str, object]:
    """Builds display fields for a hangman embed.

    Args:
        game (HangmanGame): The hangman game to render
        owner (discord.Member): The user that started the game

    Returns:
        dict[str, object]: String fields and style data for embed rendering
    """
    help_text = "Use /hangman commands to keep playing"
    display_data = {
        "title": f"`{game.draw_word_state()}`",
        "description": f"{help_text}\n\n```{game.draw_hang_state()}```",
        "remaining_guesses": game.remaining_guesses(),
        "guessed_letters": ", ".join(sorted(game.guesses)) or "None",
    }

    if game.failed:
        display_data["color"] = discord.Color.red()
        display_data["footer"] = f"Game over! The word was `{game.word}`!"
        return display_data

    if game.finished:
        display_data["color"] = discord.Color.green()
        display_data["footer"] = "Word guessed! Nice job!"
        return display_data

    display_data["color"] = discord.Color.gold()
    display_data["footer"] = f"Game started by {owner}"
    return display_data


class HangmanCog(cogs.BaseCog):
    """Class to define the Hangman game.

    Args:
        bot (commands.Bot): The bot instance that this cog is a part of.

    Attributes:
        games (dict): A dictionary to store ongoing games, where the keys are
                      player identifiers and the values are the current game state.
        hangman_app_group (app_commands.Group): The command group for the Hangman extension.
    """

    def __init__(self: Self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.games = {}

    hangman_app_group: app_commands.Group = app_commands.Group(
        name="hangman", description="Command Group for the Hangman Extension"
    )

    @hangman_app_group.command(
        name="start",
        description="Start a Hangman game in the current channel.",
        extras={"module": "hangman"},
    )
    async def start_game(
        self: Self, interaction: discord.Interaction, word: str
    ) -> None:
        """Slash command to start a hangman game.

        Args:
            interaction (discord.Interaction): The interaction object from Discord.
            word (str): The word to start the Hangman game with.
        """
        await interaction.response.defer(ephemeral=False)

        invalid_word_message = validate_start_word_input(word)
        if invalid_word_message:
            await interaction.followup.send(invalid_word_message)
            return

        normalized_word = normalize_secret_word(word)

        game_data = self.games.get(interaction.channel_id)
        if game_data:
            owner = game_data.get("user")
            conflict_action = decide_start_conflict(interaction.user.id, owner.id)

            if conflict_action == "confirm-overwrite":
                view = ui.Confirm()
                await view.send(
                    message="There is a current game in progress. Do you want to end it?",
                    channel=interaction.channel,
                    author=interaction.user,
                )
                await view.wait()
                if view.value in [
                    ui.ConfirmResponse.TIMEOUT,
                    ui.ConfirmResponse.DENIED,
                ]:
                    await interaction.followup.send("The current game was not ended.")
                    return

                del self.games[interaction.channel_id]
            else:
                await interaction.followup.send(
                    "A game is already in progress for this channel."
                )
                return

        try:
            game = HangmanGame(word=normalized_word)
        except ValueError as exception:
            await interaction.followup.send(f"Invalid word: {exception}")
            return

        embed = await self.generate_game_embed(game, interaction.user)
        message = await interaction.channel.send(embed=embed)
        self.games[interaction.channel_id] = {
            "user": interaction.user,
            "game": game,
            "message": message,
            "last_guesser": None,
        }

        await interaction.followup.send(
            "The Hangman game has started with a hidden word!"
        )

    @hangman_app_group.command(
        name="guess",
        description="Guesses a letter for the current hangman game",
        extras={"module": "hangman"},
    )
    async def guess(self: Self, interaction: discord.Interaction, letter: str) -> None:
        """Guesses a letter in a running hangman game.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            letter (str): The guessed letter
        """
        await interaction.response.defer(ephemeral=False)

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                )
            )
            return

        if interaction.user == game_data.get("user"):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "You cannot guess letters because you started this game!"
                )
            )
            return

        invalid_guess_message = validate_letter_guess_input(letter)
        if invalid_guess_message:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(invalid_guess_message)
            )
            return

        game = game_data.get("game")
        normalized_letter = letter.strip().lower()
        if game.guessed(normalized_letter):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "That letter has already been guessed"
                )
            )
            return

        correct = game.guess(normalized_letter)
        embed = await self.generate_game_embed(game, game_data.get("user"))
        message = game_data.get("message")
        await message.edit(embed=embed)

        content = build_letter_guess_result(normalized_letter, correct)
        if game.finished:
            content = f"{content} - game finished! The word was {game.word}"
            del self.games[interaction.channel.id]
        await interaction.followup.send(content=content)

    @hangman_app_group.command(
        name="solve",
        description="Guesses the full word for the current hangman game",
        extras={"module": "hangman"},
    )
    async def solve(self: Self, interaction: discord.Interaction, word: str) -> None:
        """Attempts to solve a running hangman game with a full-word guess.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            word (str): The full-word guess
        """
        await interaction.response.defer(ephemeral=False)

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                )
            )
            return

        if interaction.user == game_data.get("user"):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "You cannot guess the word because you started this game!"
                )
            )
            return

        invalid_guess_message = validate_solve_guess_input(word)
        if invalid_guess_message:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(invalid_guess_message)
            )
            return

        game = game_data.get("game")
        normalized_word = normalize_secret_word(word)
        correct = evaluate_solve_attempt(game.word, normalized_word)

        if correct:
            for letter in game.word:
                game.guesses.add(letter.lower())
        else:
            game.step += 1

        embed = await self.generate_game_embed(game, game_data.get("user"))
        message = game_data.get("message")
        await message.edit(embed=embed)

        content = build_solve_result(normalized_word, correct)
        if game.finished:
            content = f"{content} - game finished! The word was {game.word}"
            del self.games[interaction.channel.id]
        await interaction.followup.send(content=content)

    async def generate_game_embed(
        self: Self,
        game: HangmanGame,
        owner: discord.Member,
    ) -> discord.Embed:
        """Generates an embed representing the current state of the Hangman game.

        Args:
            game (HangmanGame): The current game to render
            owner (discord.Member): The owner of the game

        Returns:
            discord.Embed: The embed for the current game state
        """
        display_data = build_game_display_data(game, owner)

        embed = discord.Embed(
            title=display_data["title"],
            description=display_data["description"],
            color=display_data["color"],
        )

        if not game.finished:
            embed.add_field(
                name=f"Remaining Guesses {str(display_data['remaining_guesses'])}",
                value="\u200b",
                inline=False,
            )
            embed.add_field(
                name="Guessed Letters",
                value=display_data["guessed_letters"],
                inline=False,
            )

        embed.set_footer(text=display_data["footer"])
        return embed

    @hangman_app_group.command(
        name="redraw",
        description="Redraws the current hangman game",
        extras={"module": "hangman"},
    )
    async def redraw(self: Self, interaction: discord.Interaction) -> None:
        """Makes a new embed with a new drawing of the running hangman game.

        Args:
            interaction (discord.Interaction): The interaction in which the command was used
        """
        await interaction.response.defer(ephemeral=False)

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                )
            )
            return

        old_message = game_data.get("message")
        try:
            await old_message.delete()
        except discord.errors.NotFound:
            pass

        embed = await self.generate_game_embed(
            game_data.get("game"), game_data.get("user")
        )
        new_message = await interaction.channel.send(embed=embed)
        game_data["message"] = new_message

        await interaction.followup.send("The game board has been redrawn")

    @hangman_app_group.command(
        name="stop",
        description="Stops the current channel game",
        extras={"module": "hangman"},
    )
    async def stop(self: Self, interaction: discord.Interaction) -> None:
        """Stops the running hangman game in the current channel.

        Args:
            interaction (discord.Interaction): The interaction in which stop was run
        """
        await interaction.response.defer(ephemeral=False)

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                )
            )
            return

        game_owner = game_data.get("user")
        config = self.bot.guild_configs[str(interaction.guild.id)]
        configured_roles = config.extensions.hangman.hangman_roles.value
        caller_roles = [role.name for role in getattr(interaction.user, "roles", [])]

        deny_reason = build_stop_permission_denial(
            caller_id=interaction.user.id,
            owner_id=getattr(game_owner, "id", None),
            configured_role_names=configured_roles,
            caller_role_names=caller_roles,
        )
        if deny_reason:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(deny_reason)
            )
            return

        view = ui.Confirm()
        await view.send(
            message="Are you sure you want to end the current game?",
            channel=interaction.channel,
            author=interaction.user,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed("The current game was not ended")
            )
            return

        game = game_data.get("game")
        word = getattr(game, "word", "???")

        del self.games[interaction.channel.id]
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed(
                f"That game is now finished. The word was: `{word}`"
            )
        )

    @hangman_app_group.command(
        name="add-guesses",
        description="Allows the creator of the game to give more guesses",
        extras={"module": "hangman"},
    )
    async def add_guesses(
        self: Self, interaction: discord.Interaction, number_of_guesses: int
    ) -> None:
        """Allows the game creator to add more guesses.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            number_of_guesses (int): The number of guesses to add
        """
        await interaction.response.defer(ephemeral=False)

        if number_of_guesses <= 0:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "The number of guesses must be a positive integer."
                )
            )
            return

        game_data = self.games.get(interaction.channel.id)
        if not game_data:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "There is no game in progress for this channel"
                )
            )
            return

        game_author = game_data.get("user")
        if interaction.user.id != game_author.id:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "Only the creator of the game can add more guesses."
                )
            )
            return

        game = game_data.get("game")
        game.add_guesses(number_of_guesses)

        embed = await self.generate_game_embed(game, game_data.get("user"))
        message = game_data.get("message")
        await message.edit(embed=embed)

        await interaction.followup.send(
            content=build_add_guesses_result(
                number_of_guesses, game.remaining_guesses()
            )
        )
