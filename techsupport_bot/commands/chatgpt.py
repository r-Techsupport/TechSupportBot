"""
Name: Chatgpt
Info: Pushes a command to the chatgpt api
Unit tests: None
Config: API key in config.yml
API: OpenAI
Databases: None
Models: None
Subcommands: gpt, gptutil (history, clean)
Defines: None
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import expiringdict
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the ChatGPT plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.openai:
            raise AttributeError("ChatGPT was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("ChatGPT was not loaded due to missing API key") from exc

    await bot.add_cog(ChatGPT(bot=bot))


class ChatGPT(cogs.BaseCog):
    """Main extension class"""

    API_URL = "https://api.openai.com/v1/chat/completions"

    async def preconfig(self) -> None:
        """Sets up the dict"""
        self.history = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=3600,
        )

    SYSTEM_PROMPT = [
        {
            "role": "system",
            "content": (
                "The following questions are being asked via a Discord bot. "
                + "Please try to keep messages informative but concise. For example, "
                + "in code responses please try to not have a lot of newlines if"
                " unnecessary."
                + "The max message size should always be under 2000 characters "
                + "or it will get clipped."
            ),
        }
    ]

    async def call_api(self, ctx: commands.Context, api_key: str, prompt: str) -> str:
        """Calls the API with the history as well as the new prompt

        Args:
            ctx (commands.Context): Context of the command invokation
            api_key (str): The OpenAI API key
            prompt (str): The prompt to push to the api

        Returns:
            str: The ChatGPT response
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # [Messages] contains the history as well as the newest prompt
        data = {
            "model": "gpt-3.5-turbo",
            "messages": (
                self.SYSTEM_PROMPT
                + self.history.get(ctx.author.id, [])
                + [{"role": "user", "content": prompt}]
            ),
        }
        response = await self.bot.http_functions.http_call(
            "post", self.API_URL, headers=headers, json=data
        )
        return response

    @auxiliary.with_typing
    @commands.command(
        brief="Prompts ChatGPT",
        description="Issues a prompt to the ChatGPT API",
        usage="[prompt]",
    )
    async def gpt(self, ctx: commands.Context, *, prompt: str) -> None:
        """Pushes a prompt to the OpenAI API for ChatGPT

        Args:
            ctx (commands.Context): Context of the invokation
            prompt (str): The prompt to push
        """
        # -> Gets the API key <-
        api_key = self.bot.file_config.api.api_keys.openai
        if not api_key:
            await auxiliary.send_deny_embed(
                message="I couldn't find the OpenAI API key", channel=ctx.channel
            )
            return

        # -> Calls the API <-
        response = await self.call_api(ctx, api_key, prompt)

        # -> Response processing <-
        config = self.bot.guild_configs[str(ctx.guild.id)]
        choices = response.get("choices", [])
        if not choices:
            # Tries to figure out what error happened
            if error := response.get("error", []):
                channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=(
                        "OpenAI API responded with an error! Contents:"
                        f" {error['message']}"
                    ),
                    level=LogLevel.WARNING,
                    channel=channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )

            await auxiliary.send_deny_embed(
                message="I couldn't figure out what to say!", channel=ctx.channel
            )
            return

        response = choices[0].get("message", {}).get("content")
        if not response:
            await auxiliary.send_deny_embed(
                message="I couldn't figure out what to say!", channel=ctx.channel
            )
            return

        # Creates the history entry for the given user and appens the prompt and the result to it
        if not self.history.get(ctx.author.id):
            self.history[ctx.author.id] = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ]
        # If the history exists, just appends the prompt and the result to it
        else:
            self.history[ctx.author.id].append({"role": "user", "content": prompt})
            self.history[ctx.author.id].append(
                {"role": "assistant", "content": response}
            )

        # Finally, sends the result to the chat in plaintext
        await ctx.send(content=response[:2000])

    @commands.group(
        brief="Executes a ChatGPT utility command",
        description="Executes a ChatGPT utility command",
    )
    async def gptutil(self, ctx: commands.Context) -> None:
        """Defines the Gptutil command group for history management

        Args:
            ctx (commands.Context): Context of the invokation
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @gptutil.command(
        name="clear",
        brief="Clears history",
        description="Clears your ChatGPT conversation history",
    )
    async def clear_history(self, ctx: commands.Context) -> None:
        """Command to clear the invokers result history

        Args:
            ctx (commands.Context): Context of the invokation
        """
        # If the history for the invoker doesn't exist
        if self.history is None and ctx.author.id not in self.history:
            await auxiliary.send_deny_embed(
                message=f"No history found for {ctx.author.mention}",
                channel=ctx.channel,
            )
            return

        # Deletion confirmation
        view = ui.Confirm()
        await view.send(
            message="Clear your conversation history?",
            channel=ctx.channel,
            author=ctx.author,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message="Conversation history was not cleared", channel=ctx.channel
            )
            return

        # Finally, removes the entry
        self.history.pop(ctx.author.id, None)

        await auxiliary.send_confirm_embed(
            message="Chat history cleared!", channel=ctx.channel
        )

    @auxiliary.with_typing
    @gptutil.command(
        name="history",
        brief="Gets history",
        description="Gets your ChatGPT conversation history",
    )
    async def get_history(self, ctx: commands.Context) -> None:
        """Command to get the history of the invoker

        Args:
            ctx (commands.Context): Context of the invokation
        """
        # Gets the history, makes sure it is valid
        history = self.history.get(ctx.author.id)
        if history is None:
            await auxiliary.send_deny_embed(
                message=f"No history found for {ctx.author.mention}",
                channel=ctx.channel,
            )
            return

        # Creates the embeds for pagination
        embeds = []
        for i in range(0, len(history), 2):
            prompt = history[i].get("content", "Unknown").strip()
            resp = history[i + 1].get("content", "Unknown").strip()

            embed = discord.Embed(title="ChatGPT History")
            embed.add_field(name="Prompt", value=prompt[:255])
            embed.add_field(name="Response", value=resp[:255])

            embeds.append(embed)

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)
