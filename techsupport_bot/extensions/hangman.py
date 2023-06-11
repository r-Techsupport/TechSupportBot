"""Module for the hangman extension for the bot."""
import datetime
import uuid

import base
import discord
import ui
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Add hangman extension to the config file."""
    config = bot.ExtensionConfig()
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
    """Class for the game hangman."""

    HANG_PICS = [
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
        """
        +---+
        |   |
        O   |
       /|   |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
       /|\  |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
       /|\  |
       /    |
            |
        =========""",
        """
        +---+
        |   |
        O   |
       /|\  |
       / \  |
            |
        =========""",
    ]
    FINAL_STEP = len(HANG_PICS) - 1

    def __init__(self, **kwargs):
        word = kwargs.pop("word")
        if not word or "_" in word or not word.isalpha():
            raise ValueError("valid word must be provided")
        self.word = word
        self.guesses = set()
        self.step = 0
        self.started = datetime.datetime.utcnow()
        self.id = uuid.uuid4()

    def draw_word_state(self):
        """Method to draw the word on the embed."""
        state = ""
        for letter in self.word:
            value = letter if letter.lower() in self.guesses else "_"
            state += f" {value} "

        return state

    def draw_hang_state(self):
        """Method to draw the current state of the game."""
        return self.HANG_PICS[self.step]

    def guess(self, letter):
        """Method to define a guess."""
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
    def finished(self):
        """Method to finish the game of hangman."""
        if self.step < 0 or self.step >= self.FINAL_STEP:
            return True
        if all(letter in self.guesses for letter in self.word):
            return True
        return False

    @property
    def failed(self):
        """Method in case the game wasn't successful."""
        if self.step >= self.FINAL_STEP:
            return True
        return False

    def guessed(self, letter):
        """Method to know if a guess has already been guessed."""
        if len(letter) > 1:
            raise ValueError("guess must be letter")
        if letter.lower() in self.guesses:
            return True
        return False


async def can_stop_game(ctx):
    """Method to stop the game of hangman at any time."""
    cog = ctx.bot.get_cog("HangmanCog")
    if not cog:
        raise AttributeError("could not find hangman cog when checking game states")

    game_data = cog.games.get(ctx.channel.id)
    user = game_data.get("user")
    if getattr(user, "id", 0) == ctx.author.id:
        return True

    config = await ctx.bot.get_context_config(ctx)
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


class HangmanCog(base.BaseCog):
    """Class to define the hangman game."""

    async def preconfig(self):
        """Method to preconfig the game."""
        self.games = {}

    @commands.guild_only()
    @commands.group(
        name="hangman", description="Runs a hangman command", aliases=["hm"]
    )
    async def hangman(self, ctx):
        """Method to use the command to start the hangman game."""

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

        pass

    @hangman.command(
        name="start",
        description="Starts a hangman game in the current channel",
        usage="[word]",
    )
    async def start_game(self, ctx, word: str):
        """Method to start the hangman game and delete the original message."""
        # delete the message so the word is not seen
        await ctx.message.delete()

        game_data = self.games.get(ctx.channel.id)
        if game_data:
            # if there is a game currently,
            # get user who started it
            user = game_data.get("user")
            if getattr(user, "id", 0) == ctx.author.id:
                view = ui.Confirm()
                await view.send(
                    message="There is a current game in progress. Would you like to end it?",
                    channel=ctx.channel,
                    author=ctx.author,
                )

                await view.wait()
                if view.value is ui.ConfirmResponse.TIMEOUT:
                    return
                if view.value is ui.ConfirmResponse.DENIED:
                    await auxiliary.send_deny_embed(
                        message="The current game was not ended", channel=ctx.channel
                    )
                    return

                del self.games[ctx.channel.id]
            else:
                await auxiliary.send_deny_embed(
                    message="There is a game in progress for this channel",
                    channel=ctx.channel,
                )
                return

        game = HangmanGame(word=word)
        embed = await self.generate_game_embed(ctx, game)
        message = await ctx.channel.send(embed=embed)
        self.games[ctx.channel.id] = {
            "user": ctx.author,
            "game": game,
            "message": message,
            "last_guesser": None,
        }

    @hangman.command(
        name="guess",
        description="Guesses a letter for the current hangman game",
        usage="[letter]",
    )
    async def guess(self, ctx, letter: str):
        """Method to define a guess on the hangman game."""
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

    async def generate_game_embed(self, ctx, game):
        """Method to make the game into an embed."""
        hangman_drawing = game.draw_hang_state()
        hangman_word = game.draw_word_state()

        prefix = await self.bot.get_prefix(ctx.message)
        embed = discord.Embed(
            title=f"`{hangman_word}`",
            description=f"Type `{prefix}help extension hangman` for more info\n\n ```{hangman_drawing}```",
        )

        if game.failed:
            embed.color = discord.Color.red()
            footer_text = f"Game over! The word was `{game.word}`!"
        elif game.finished:
            embed.color = discord.Color.green()
            footer_text = "Word guessed! Nice job!"
        else:
            embed.color = discord.Color.gold()
            footer_text = f"{game.FINAL_STEP - game.step} wrong guesses left!"

        embed.set_footer(text=footer_text)

        return embed

    @hangman.command(name="redraw", description="Redraws the current hangman game")
    async def redraw(self, ctx):
        """Method to redraw the current status of the hangman game."""
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
        except Exception:
            pass

        embed = await self.generate_game_embed(ctx, game_data.get("game"))
        new_message = await ctx.send(embed=embed)
        game_data["message"] = new_message

    @commands.check(can_stop_game)
    @hangman.command(name="stop", description="Stops the current channel game")
    async def stop(self, ctx):
        """Method to determine if the game is finished and stop the game."""
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
