import datetime
import uuid

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[HangmanCog])


class HangmanGame:

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
        /|  |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
        /|\ |
            |
            |
        =========""",
        """
        +---+
        |   |
        O   |
        /|\ |
        /   |
            |
        =========""",
        """
        +---+
        |   |
        O   |
        /|\ |
        / \ |
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
        state = ""
        for letter in self.word:
            value = letter if letter.lower() in self.guesses else "_"
            state += f" {value} "

        return state

    def draw_hang_state(self):
        return self.HANG_PICS[self.step]

    def guess(self, letter):
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
        if self.step < 0 or self.step >= self.FINAL_STEP:
            return True
        if all(letter in self.guesses for letter in self.word):
            return True
        return False

    @property
    def failed(self):
        if self.step >= self.FINAL_STEP:
            return True
        return False

    def guessed(self, letter):
        if len(letter) > 1:
            raise ValueError("guess must be letter")
        if letter.lower() in self.guesses:
            return True
        return False


class HangmanCog(base.BaseCog):
    async def preconfig(self):
        self.games = {}

    @commands.group(name="hangman", description="Runs a hangman command")
    async def hangman(self, ctx):
        pass

    @hangman.command(
        name="start",
        description="Starts a hangman game in the current channel",
        usage="[word]",
    )
    async def start_game(self, ctx, word: str):
        # delete the message so the word is not seen
        await ctx.message.delete()

        game_data = self.games.get(ctx.channel.id)
        if game_data:
            # if there is a game currently,
            # get user who started it
            user = game_data.get("user")
            if getattr(user, "id", 0) == ctx.author.id:
                should_delete = await self.bot.confirm(
                    ctx,
                    "There is a current game in progress that you started. Would you like to end it?",
                    delete_after=True,
                )
                if not should_delete:
                    return
                del self.games[ctx.channel.id]
            else:
                await util.send_with_mention(
                    ctx, "There is a game in progress for this channel"
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
        if len(letter) > 1 or not letter.isalpha():
            await util.send_with_mention(ctx, "You can only guess a letter")
            return

        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await util.send_with_mention(
                ctx, "There is no game in progress for this channel"
            )
            return

        game = game_data.get("game")

        if game.guessed(letter):
            await util.send_with_mention(ctx, "That letter has already been guessed")
            return

        correct = game.guess(letter)
        embed = await self.generate_game_embed(ctx, game)
        message = game_data.get("message")
        await message.edit(embed=embed)

        content = f"Found `{letter}`" if correct else f"Letter `{letter}` not in word"
        if game.finished:
            content = f"{content} - game finished!"
        await util.send_with_mention(ctx, content)

    async def generate_game_embed(self, ctx, game):
        hangman_drawing = game.draw_hang_state()
        hangman_word = game.draw_word_state()

        prefix = await self.bot.get_prefix(ctx.message)
        embed = discord.Embed(
            title=f"`{hangman_word}`",
            description=f"Type `{prefix}help hangman` for more info\n\n ```{hangman_drawing}```",
        )

        if game.failed:
            embed.color = discord.Color.red()
            footer_text = "Game over!"
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
        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await util.send_with_mention(
                ctx, "There is no game in progress for this channel"
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

    @commands.has_permissions(kick_members=True)
    @hangman.command(name="stop", description="Stops the current channel game")
    async def stop(self, ctx):
        game_data = self.games.get(ctx.channel.id)
        if not game_data:
            await util.send_with_mention(
                ctx, "There is no game in progress for this channel"
            )
            return

        should_delete = await self.bot.confirm(
            ctx,
            "Are you sure you want to end the current game?",
            delete_after=True,
        )

        if not should_delete:
            return

        game = game_data.get("game")
        word = getattr(game, "word", "???")

        del self.games[ctx.channel.id]
        await util.send_with_mention(
            ctx, f"That game is now finished. The word was: `{word}`"
        )
