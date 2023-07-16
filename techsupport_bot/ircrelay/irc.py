import asyncio
import base64
import logging
import threading
import time

import discord
import irc.bot
import irc.strings
from ircrelay import formatting


class IRCBot(irc.bot.SingleServerIRCBot):
    irc_cog = None
    loop = None
    console = logging.getLogger("root")
    IRC_BOLD = ""
    connection = None
    join_thread = None

    def __init__(self, loop, server, port, channels, username, password):
        self.loop = loop
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], username, username)
        self.join_channel_list = channels
        self.username = username
        self.password = password

    def on_nicknameinuse(self, connection, event):
        connection.nick(connection.get_nickname() + "_")

    def on_welcome(self, connection, event):
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

    def join_channels(self, connection):
        for channel in self.join_channel_list:
            if channel in self.channels:
                continue
            self.console.info(f"Joining {channel}")
            connection.join(channel)

    def join_channels_thread(self):
        self.join_channels(self.connection)
        if self.join_thread and self.join_thread.is_alive():
            self.join_thread.cancel()
        self.join_thread = threading.Timer(600, self.join_channels_thread)
        self.join_thread.start()

    def on_part(self, connection, event):
        if event.target == self.username:
            self.join_channels(connection)

    def on_privmsg(self, connection, event):
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.handle_dm_from_irc(event.arguments[0], event.source), self.loop
        )

    def on_pubmsg(self, connection, event):
        split_message = formatting.parse_irc_message(event)
        if len(split_message) == 0:
            return
        self.send_message_to_discord(split_message)

    def send_message_to_discord(self, split_message):
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.send_message_from_irc(split_message), self.loop
        )

    def get_irc_status(self):
        if self.connection.is_connected():
            status_text = "IRC is connected and working"
        else:
            status_text = "IRC is not connected"
        return {
            "status": status_text,
            "name": self.username,
            "channels": ", ".join(self.channels.keys()),
        }

    def send_edit_from_discord(self, message, channel):
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_edit_message(message)
        self.send_message_to_channel(channel, formatted_message)

    def send_reaction_from_discord(
        self, reaction: discord.Reaction, user: discord.User, channel: str
    ):
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_reaction_message(
            reaction.message, user, reaction
        )
        self.send_message_to_channel(channel, formatted_message)

    def send_message_from_discord(self, message, channel):
        """Sends a message from discord to IRC

        Args:
            message (discord.Message): The raw string content of the message
            channel (str): The IRC channel name
        """
        if channel not in self.channels:
            self.join_channels(self.connection)
        formatted_message = formatting.format_discord_message(message)
        self.send_message_to_channel(channel, formatted_message)

    def send_message_to_channel(self, channel, message):
        message_list = [message[i : i + 450] for i in range(0, len(message), 450)]
        for message in message_list:
            self.connection.privmsg(channel, message)

    def on_mode(self, connection, event):
        print(event)
        # Parse the mode change event
        modes = event.arguments[0].split()
        # The first element of `modes` is the mode being set or removed
        mode = modes[0]

        # Assuming you have a function named `on_user_mode_change` that you want to call
        # when someone gets banned/unbanned. You can modify the condition accordingly.
        if mode in ("+b", "-b"):
            message = formatting.parse_ban_message(event)
            self.send_message_to_discord(message)

    def on_user_mode_change(self, channel, action, user):
        # This is where you handle the event when someone gets banned or unbanned.
        # You can implement your custom logic here.
        print(f"{user} has been {action} from channel {channel}")

    def ban_on_irc(self, user: str, channel: str, action: str):
        self.connection.mode(channel, f"{action} {user}")

    def is_bot_op_on_channel(self, channel_name):
        return self.channels[channel_name].is_oper(self.username)
