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


async def can_stop_game(ctx: commands.Context) -> bool:
    """
    Checks if a user has the ability to stop the running game

    Args:
        ctx (commands.Context): The context in which the stop command was run

    Raises:
        AttributeError: The Hangman game could not be found
        CommandError: No admin roles have been defined in the config
        MissingAnyRole: The doesn't have the admin roles needed to stop the game

    Returns:
        bool: True the user can stop the game, False they cannot
    """
    cog = ctx.bot.get_cog("HangmanCog")
    if not cog:
        raise AttributeError("could not find hangman cog when checking game states")

    game_data = cog.games.get(ctx.channel.id)
    user = game_data.get("user")
    if getattr(user, "id", 0) == ctx.author.id:
        return True

    config = ctx.bot.guild_configs[str(ctx.guild.id)]
    roles = []
    for role_name in config.extensions.hangman.hangman_roles.value:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            continue
        roles.append(role)

    if not roles:
        raise commands.CommandError("no hangman admin roles found")

    if not any(role in ctx.author.roles for role in roles):
        raise commands.MissingAnyRole(roles)

    return True


class HangmanCog(cogs.BaseCog):
    """Class to define the hangman game.

    Args:
        bot (commands.Bot): The bot instance that this cog is a part of.
    """

    def __init__(self, bot):
        """Initialize the HangmanCog with the given bot instance.

        Args:
            bot (commands.Bot): The bot instance that this cog is a part of.
        """

        super().__init__(bot)
        self.games = {}

    @commands.guild_only()
    @commands.group(
        name="hangman", description="Runs a hangman command", aliases=["hm"]
    )
    async def hangman(self: Self, ctx: commands.Context) -> None:
        """The bare .hangman command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @app_commands.command(
        name="start_hangman",
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
        # Ensure only the command's author can see this interaction
        await interaction.response.defer(ephemeral=True)

        # Check if a game is already active in the channel
        game_data = self.games.get(interaction.channel_id)
        if game_data:
            # Check if the game owner wants to overwrite the current game
            user = game_data.get("user")
            if user.id == interaction.user.id:
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
                    await interaction.followup.send(
                        "The current game was not ended.", ephemeral=True
                    )
                    return

                # Remove the existing game
                del self.games[interaction.channel_id]
            else:
                await interaction.followup.send(
                    "A game is already in progress for this channel.", ephemeral=True
                )
                return

        # Validate the provided word
        try:
            game = HangmanGame(word=word.lower())
        except ValueError as e:
            await interaction.followup.send(f"Invalid word: {e}", ephemeral=True)
            return

        # Create and send the initial game embed
        embed = await self.generate_game_embed(interaction, game)
        message = await interaction.channel.send(embed=embed)
        self.games[interaction.channel_id] = {
            "user": interaction.user,
            "game": game,
            "message": message,
            "last_guesser": None,
        }

        await interaction.followup.send(
            "The Hangman game has started with a hidden word!", ephemeral=True
        )

    @hangman.command(
        name="guess",
        description="Guesses a letter for the current hangman game",
        usage="[letter]",
    )
    async def guess(self: Self, ctx: commands.Context, letter: str) -> None:
        """Discord command to guess a letter in a running hangman game

        Args:
            ctx (commands.Context): The context in which the command was run in
            letter (str): The letter the user is trying to guess
        """
        game_data = self.games.get(ctx.channel.id)
        if ctx.author == game_data.get("user"):
            await auxiliary.send_deny_embed(
                message="You cannot guess letters because you started this game!",
                channel=ctx.channel,
            )
            return

        if len(letter) > 1 or not letter.isalpha():
            await auxiliary.send_deny_embed(
                message="You can only guess a letter", channel=ctx.channel
            )
            return

        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await auxiliary.send_deny_embed(
                message="There is no game in progress for this channel",
                channel=ctx.channel,
            )
            return

        game = game_data.get("game")

        if game.guessed(letter):
            await auxiliary.send_deny_embed(
                message="That letter has already been guessed", channel=ctx.channel
            )
            return

        correct = game.guess(letter)
        embed = await self.generate_game_embed(ctx, game)
        message = game_data.get("message")
        await message.edit(embed=embed)

        content = f"Found `{letter}`" if correct else f"Letter `{letter}` not in word"
        if game.finished:
            content = f"{content} - game finished! The word was {game.word}"
            del self.games[ctx.channel.id]
        await ctx.send(content=content)

    async def generate_game_embed(
        self: Self,
        ctx_or_interaction: discord.Interaction | commands.Context,
        game: HangmanGame,
    ) -> discord.Embed:
        """
        Generates an embed representing the current state of the Hangman game.

        Args:
            ctx_or_interaction (discord.Interaction | commands.Context):
                The context or interaction used to generate the embed, which provides
                information about the user and the message.
            game (HangmanGame): The current instance of the Hangman game, used to
                retrieve game state, including word state, remaining guesses, and the
                hangman drawing.

        Returns:
            discord.Embed: An embed displaying the current game state, including
                the hangman drawing, word state, remaining guesses, guessed letters,
                and the footer indicating the game status and creator.
        """
        hangman_drawing = game.draw_hang_state()
        hangman_word = game.draw_word_state()
        # Determine the guild ID
        guild_id = None
        if isinstance(ctx_or_interaction, commands.Context):
            guild_id = ctx_or_interaction.guild.id if ctx_or_interaction.guild else None
        elif isinstance(ctx_or_interaction, discord.Interaction):
            guild_id = ctx_or_interaction.guild_id

        # Fetch the prefix manually since get_prefix expects a Message
        if guild_id and str(guild_id) in self.bot.guild_configs:
            prefix = self.bot.guild_configs[str(guild_id)].command_prefix
        else:
            prefix = self.file_config.bot_config.default_prefix

        embed = discord.Embed(
            title=f"`{hangman_word}`",
            description=(
                f"Type `{prefix}help hangman` for more info\n\n"
                f"```{hangman_drawing}```"
            ),
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

            # Determine the game creator based on interaction type
            if isinstance(ctx_or_interaction, discord.Interaction):
                footer_text = f"Game started by {ctx_or_interaction.user}"
            elif isinstance(ctx_or_interaction, commands.Context):
                footer_text = f"Game started by {ctx_or_interaction.author}"
            else:
                footer_text = " "

        embed.set_footer(text=footer_text)
        return embed

    @hangman.command(name="redraw", description="Redraws the current hangman game")
    async def redraw(self: Self, ctx: commands.Context) -> None:
        """A discord command to make a new embed with a new drawing of the running hangman game
        This redraws the hangman game being played in the current channel

        Args:
            ctx (commands.Context): The context in which the command was in
        """
        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await auxiliary.send_deny_embed(
                message="There is no game in progress for this channel",
                channel=ctx.channel,
            )
            return

        old_message = game_data.get("message")
        try:
            await old_message.delete()
        except discord.errors.NotFound:
            pass

        embed = await self.generate_game_embed(ctx, game_data.get("game"))
        new_message = await ctx.send(embed=embed)
        game_data["message"] = new_message

    @commands.check(can_stop_game)
    @hangman.command(name="stop", description="Stops the current channel game")
    async def stop(self: Self, ctx: commands.Context) -> None:
        """Checks if a user can stop the hangman game in the current channel
        If they can, the game is stopped

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await auxiliary.send_deny_embed(
                "There is no game in progress for this channel", channel=ctx.channel
            )
            return

        view = ui.Confirm()
        await view.send(
            message="Are you sure you want to end the current game?",
            channel=ctx.channel,
            author=ctx.author,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                "The current game was not ended", channel=ctx.channel
            )
            return

        game = game_data.get("game")
        word = getattr(game, "word", "???")

        del self.games[ctx.channel.id]
        await auxiliary.send_confirm_embed(
            message=f"That game is now finished. The word was: `{word}`",
            channel=ctx.channel,
        )

    @hangman.command(
        name="add_guesses",
        description="Allows the creator of the game to give more guesses",
        usage="[number_of_guesses]",
    )
    async def add_guesses(
        self: Self, ctx: commands.Context, number_of_guesses: int
    ) -> None:
        """Discord command to allow the game creator to add more guesses.

        Args:
            ctx (commands.Context): The context in which the command was run.
            number_of_guesses (int): The number of guesses to add.
        """
        if number_of_guesses <= 0:
            await auxiliary.send_deny_embed(
                message="The number of guesses must be a positive integer.",
                channel=ctx.channel,
            )
            return

        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await auxiliary.send_deny_embed(
                message="There is no game in progress for this channel.",
                channel=ctx.channel,
            )
            return

        # Ensure only the creator of the game can add guesses
        game_author = game_data.get("user")
        if ctx.author.id != game_author.id:
            await auxiliary.send_deny_embed(
                message="Only the creator of the game can add more guesses.",
                channel=ctx.channel,
            )
            return

        game = game_data.get("game")

        # Add the new guesses
        game.add_guesses(number_of_guesses)

        # Notify the channel
        await ctx.send(
            content=(
                f"{number_of_guesses} guesses have been added! "
                f"Total guesses remaining: {game.remaining_guesses()}"
            )
        )

        # Update the game embed
        embed = await self.generate_game_embed(ctx, game)
        message = game_data.get("message")
        await message.edit(embed=embed)
