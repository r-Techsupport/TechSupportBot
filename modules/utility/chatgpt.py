"""
Name: Chatgpt
Info: Pushes a command to the chatgpt api
Unit tests: None
Config: API key in config.yml
API: OpenAI
Databases: None
Models: None
Subcommands: /chatgpt chat, /chatgpt history, /chatgpt clear
Defines: None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import expiringdict
from discord import app_commands

import configuration
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs

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
    """Main extension class

    Attributes:
        chatgpt (app_commands.Group): The group for the /chatgpt commands
        API_URL (str): The URL for the openai API
        SYSTEM_PROMPT (dict[str, str]): The default starting prompt for chatGPT
    """

    API_URL: str = "https://api.openai.com/v1/chat/completions"
    chatgpt: app_commands.Group = app_commands.Group(
        name="chatgpt", description="Chat with ChatGPT and manage your history"
    )

    async def preconfig(self: Self) -> None:
        """Sets up the dict"""
        self.history = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=3600,
        )

    SYSTEM_PROMPT: list[dict[str, str]] = [
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

    async def call_api(
        self: Self, interaction: discord.Interaction, api_key: str, prompt: str
    ) -> dict:
        """Calls the API with the history as well as the new prompt

        Args:
            interaction (discord.Interaction): The interaction that called the command
            api_key (str): The OpenAI API key
            prompt (str): The prompt to push to the api

        Returns:
            dict: The ChatGPT response
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
                + self.history.get(interaction.user.id, [])
                + [{"role": "user", "content": prompt}]
            ),
        }
        response = await self.bot.http_functions.http_call(
            "post", self.API_URL, headers=headers, json=data
        )
        return response

    @chatgpt.command(
        name="chat",
        description="Issues a prompt to the ChatGPT API",
    )
    async def chat(self: Self, interaction: discord.Interaction, prompt: str) -> None:
        """Pushes a prompt to the OpenAI API for ChatGPT

        Args:
            interaction (discord.Interaction): The interaction that called the command
            prompt (str): The prompt to push
        """
        await interaction.response.defer()

        # -> Gets the API key <-
        api_key = self.bot.file_config.api.api_keys.openai
        if not api_key:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "I couldn't find the OpenAI API key"
                ),
            )
            return

        # -> Calls the API <-
        response = await self.call_api(interaction, api_key, prompt)

        # -> Response processing <-
        choices = response.get("choices", [])
        if not choices:
            # Tries to figure out what error happened
            if error := response.get("error", []):
                channel = configuration.get_config_entry(
                    interaction.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=(
                        "OpenAI API responded with an error! Contents:"
                        f" {error['message']}"
                    ),
                    level=LogLevel.WARNING,
                    channel=channel,
                    context=LogContext(
                        guild=interaction.guild, channel=interaction.channel
                    ),
                )

            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "I couldn't figure out what to say!"
                ),
            )
            return

        response = choices[0].get("message", {}).get("content")
        if not response:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "I couldn't figure out what to say!"
                ),
            )
            return

        # Creates the history entry for the given user and appens the prompt and the result to it
        if not self.history.get(interaction.user.id):
            self.history[interaction.user.id] = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ]
        # If the history exists, just appends the prompt and the result to it
        else:
            self.history[interaction.user.id].append(
                {"role": "user", "content": prompt}
            )
            self.history[interaction.user.id].append(
                {"role": "assistant", "content": response}
            )

        embed = discord.Embed(
            description=response[:4096], color=discord.Color.blurple()
        )
        await interaction.followup.send(embed=embed)

    @chatgpt.command(
        name="clear",
        description="Clears your ChatGPT conversation history",
    )
    async def clear_history(self: Self, interaction: discord.Interaction) -> None:
        """Command to clear the invokers result history

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        await interaction.response.defer(ephemeral=True)
        # If the history for the invoker doesn't exist
        if not self.history.get(interaction.user.id):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    f"No history found for {interaction.user.mention}"
                ),
                ephemeral=True,
            )
            return

        # Deletion confirmation
        view = ui.Confirm()
        await view.send(
            message="Clear your conversation history?",
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
            ephemeral=True,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "Conversation history was not cleared"
                ),
                ephemeral=True,
            )
            return

        # Finally, removes the entry
        self.history.pop(interaction.user.id, None)

        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed("Chat history cleared!"),
            ephemeral=True,
        )

    @chatgpt.command(
        name="history",
        description="Gets your ChatGPT conversation history",
    )
    async def get_history(self: Self, interaction: discord.Interaction) -> None:
        """Command to get the history of the invoker

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        await interaction.response.defer(ephemeral=True)
        # Gets the history, makes sure it is valid
        history = self.history.get(interaction.user.id)
        if not history:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    f"No history found for {interaction.user.mention}"
                ),
                ephemeral=True,
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

        await ui.PaginateView().send(
            interaction.channel, interaction.user, embeds, interaction, ephemeral=True
        )
