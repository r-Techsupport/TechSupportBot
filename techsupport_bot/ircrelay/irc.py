import asyncio
import base64
import logging
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

    def join_channels(self, connection):
        for channel in self.join_channel_list:
            self.console.info(f"Joining {channel}")
            connection.join(channel)

    def on_privmsg(self, connection, event):
        print("Do something with DMs on IRC here")
        self.do_command(event, event.arguments[0])

    def on_pubmsg(self, connection, event):
        split_message = formatting.parse_irc_message(event)
        self.send_message_to_discord(split_message)
    
    def send_message_to_discord(self, split_message):
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.send_message_from_irc(split_message), self.loop
        )

    def format_message(self, message: discord.Message):
        """This formats the message from discord to prepare for sending to IRC
        Strips new lines and trailing white space

        Args:
            message (discord.Message): The discord message to convert

        Returns:
            str: The formatted message, ready to send to IRC
        """
        permissions_prefix = self.get_permissions_prefix(message.author)
        message_str = f"{self.IRC_BOLD}[D]{self.IRC_BOLD} <{permissions_prefix}"
        message_str += f"{message.author.display_name}> {message.clean_content}"
        message_str = message_str.replace("\n", " ")
        return message_str.strip()

    def get_permissions_prefix(self, member: discord.Member):
        """Gets the correct prefix based on permissions to prefix in IRC

        Args:
            member (discord.Member): The member object who sent the message in discord

        Returns:
            str: The string containing the prefix. Could be empty
        """
        prefix_str = ""
        if member.guild_permissions.administrator:
            prefix_str += "*"
        if member.guild_permissions.ban_members:
            prefix_str += "*"
        return prefix_str

    def send_message_from_discord(self, message, channel):
        """Sends a message from discord to IRC

        Args:
            message (discord.Message): The raw string content of the message
            channel (str): The IRC channel name
        """
        formatted_message = self.format_message(message)
        self.connection.privmsg(channel, formatted_message)
    
    def on_mode(self, connection, event):
        print(event)
        # Parse the mode change event
        modes = event.arguments[0].split()
        # The first element of `modes` is the mode being set or removed
        mode = modes[0]

        # Assuming you have a function named `on_user_mode_change` that you want to call
        # when someone gets banned/unbanned. You can modify the condition accordingly.
        if mode in ('+b', '-b'):
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
