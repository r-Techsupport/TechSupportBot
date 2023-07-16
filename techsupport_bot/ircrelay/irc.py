"""This is the core of the IRC bot. It connects to IRC and handles message tranmissions to discord"""
import asyncio
import base64
import logging
import threading
import time
from typing import Dict, List

import discord
import irc.bot
import irc.client
import irc.strings
from ircrelay import formatting


class IRCBot(irc.bot.SingleServerIRCBot):
    """The IRC bot class. This is the class that runs the entire IRC side of the bot"""

    irc_cog = None
    loop = None
    console = logging.getLogger("root")
    IRC_BOLD = ""
    connection = None
    join_thread = None

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        server: str,
        port: int,
        channels: List[str],
        username: str,
        password: str,
    ) -> None:
        """The function to start the entire IRC bot

        Args:
            loop (asyncio.AbstractEventLoop): The running event loop for the discord API.
            server (str): The string server domain/IP
            port (int): The port the IRC server is running on
            channels (List[str]): The list of channels to join
            username (str): The username of the IRC bot account
            password (str): The password of the IRC bot account
        """
        self.loop = loop
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], username, username)
        self.join_channel_list = channels
        self.username = username
        self.password = password

    def on_nicknameinuse(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """A simple way to ensure that the bot will never be reject for an in use nickname

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        connection.nick(connection.get_nickname() + "_")

    def on_welcome(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do after the connection has been established, but before authentication
        This authenticates using SASL, joins channels, and starts a thread to auto join channels
        when needed

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        # Authenticate with SASL
        self.console.info("Authenticating to IRC")
        connection.send_raw("CAP REQ :sasl")
        connection.send_raw(f"AUTHENTICATE PLAIN")
        auth_message = f"\0{self.username}\0{self.password}"
        encoded_auth_message = base64.b64encode(auth_message.encode("UTF-8")).decode(
            "UTF-8"
        )
        connection.send_raw(f"AUTHENTICATE {encoded_auth_message}")
        time.sleep(10)
        self.console.info("Connected to IRC")
        self.join_channels(connection)
        self.connection = connection
        self.join_thread = threading.Timer(600, self.join_channels_thread)
        self.join_thread.start()

    def join_channels(self, connection: irc.client.ServerConnection) -> None:
        """Joins all channels from the list of channels in self.join_channel_list

        Args:
            connection (irc.client.ServerConnection): The IRC connection
        """
        for channel in self.join_channel_list:
            if channel in self.channels:
                continue
            self.console.info(f"Joining {channel}")
            connection.join(channel)

    def join_channels_thread(self):
        """A function called by the auto join channel thread
        This restarts the thread, and calls the join channels function
        In the event the bot ever leaves a channel for some reason, like a net split
        This will ensure that the bot rejoins them
        """
        self.join_channels(self.connection)
        if self.join_thread and self.join_thread.is_alive():
            self.join_thread.cancel()
        self.join_thread = threading.Timer(600, self.join_channels_thread)
        self.join_thread.start()

    def on_part(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        if event.target == self.username:
            self.join_channels(connection)

    def on_privmsg(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when the bot gets DMs on IRC
        Currently just sends a message to the discord bot owners DMs

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.handle_dm_from_irc(event.arguments[0], event), self.loop
        )

    def on_pubmsg(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when a message is sent in a public channel the bot is in
        If the channel is linked to a discord channel, the message will get sent to discord

        Args:
           connection (irc.client.ServerConnection): The IRC connection
           event (irc.client.Event): The event object that triggered this function
        """
        split_message = formatting.parse_irc_message(event)
        if len(split_message) == 0:
            return
        self.send_message_to_discord(split_message)

    def send_message_to_discord(self, split_message: Dict[str, str]) -> None:
        """Sends the given message to discord, using the discord API event loop

        Args:
            split_message (Dict[str, str]): The formatted message to send to discord
        """
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.send_message_from_irc(split_message), self.loop
        )

    def get_irc_status(self) -> Dict[str, str]:
        """Gets the status of the IRC bot
        Returns nicely formatted status, username, and channels

        Returns:
            Dict[str, str]: The dictionary containing the 3 status items as strings
        """
        if self.connection.is_connected():
            status_text = "Connected"
        else:
            status_text = "Not connected"
        channels = ", ".join(self.channels.keys())
        if len(channels.strip()) == 0:
            channels = "No channels"
        return {
            "status": status_text,
            "name": self.username,
            "channels": channels,
        }

    def send_edit_from_discord(self, message: discord.Message, channel: str) -> None:
        """This handles a discord message being edited

        Args:
            message (discord.Message): The message object after being edited
            channel (str): The linked IRC channel the message was sent
        """
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_edit_message(message)
        self.send_message_to_channel(channel, formatted_message)

    def send_reaction_from_discord(
        self, reaction: discord.Reaction, user: discord.User, channel: str
    ):
        """This handles a discord message getting a reaction added to it
        This does currently not handle the IRC message getting a reaction added to it

        Args:
            reaction (discord.Reaction): The reaction object that added
            user (discord.User): The user who added the reaction
            channel (str): The linked IRC channel the message reacted to is in
        """
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_reaction_message(
            reaction.message, user, reaction
        )
        self.send_message_to_channel(channel, formatted_message)

    def send_message_from_discord(self, message: discord.Message, channel: str) -> None:
        """Sends a message from discord to IRC

        Args:
            message (discord.Message): The message object that was sent on discord
            channel (str): The linked IRC channel the message was sent
        """
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_message(message)
        self.send_message_to_channel(channel, formatted_message)

    def send_message_to_channel(self, channel: str, message: str) -> None:
        """Sends a message to a channel. Splits the message if needed

        Args:
            channel (str): The IRC channel to send the message to
            message (str): The fully formatted string to send to the IRC channel
        """
        message_list = [message[i : i + 450] for i in range(0, len(message), 450)]
        for message in message_list:
            self.connection.privmsg(channel, message)

    def on_mode(
        self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when a channel mode is changed
        Currently just handles ban notifications

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        # Parse the mode change event
        modes = event.arguments[0].split()
        # The first element of `modes` is the mode being set or removed
        mode = modes[0]

        if mode in ("+b", "-b"):
            message = formatting.parse_ban_message(event)
            self.send_message_to_discord(message)

    def ban_on_irc(self, user: str, channel: str, action: str) -> None:
        """Ban or unban a given user on the specified IRC channe;

        Args:
            user (str): The hostmask of the user to modify
            channel (str): The channel to modify the user in
            action (str): The action, either +b or -b, to take on the user
        """
        self.connection.mode(channel, f"{action} {user}")

    def is_bot_op_on_channel(self, channel_name: str) -> bool:
        """Checking if the bot is an operator on the given channel

        Args:
            channel_name (str): The string representation of the IRC channel to check

        Returns:
            bool: True if the bot is an operator, False if it's not
        """
        return self.channels[channel_name].is_oper(self.username)
