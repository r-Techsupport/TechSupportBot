import asyncio
import base64
import logging
import socket

import discord
from irc import formatting


class IRC:
    """The IRC side of the relay"""

    irc_socket = None
    irc_cog = None
    loop = None
    console = logging.getLogger("root")
    IRC_BOLD = ""

    def __init__(self, loop):
        self.loop = loop

    def connect_irc(
        self, server: str, port: int, channels: list, name: str, password: str
    ):
        """This connects to the provided IRC server over SASL

        Args:
            server (str): The URL of the server
            port (int): THe port the IRC server runs on
            channels (list): The list of channels that should be joined
            name (str): The username of the IRC account
            password (str): The password of the IRC account

        Returns:
            socket.socket: The socket created by authentication
        """
        # Connect to the IRC server
        irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc_socket.connect((server, port))

        # Send user and nickname information
        irc_socket.send(bytes(f"NICK {name}\r\n", "UTF-8"))
        irc_socket.send(bytes(f"USER {name} 0 * :{name}\r\n", "UTF-8"))

        # Authenticate with SASL
        irc_socket.send(bytes("CAP REQ :sasl\r\n", "UTF-8"))
        irc_socket.send(bytes(f"AUTHENTICATE PLAIN\r\n", "UTF-8"))
        auth_message = f"\0{name}\0{password}"
        encoded_auth_message = base64.b64encode(auth_message.encode("UTF-8")).decode(
            "UTF-8"
        )
        irc_socket.send(bytes(f"AUTHENTICATE {encoded_auth_message}\r\n", "UTF-8"))

        # Wait for SASL authentication success
        while True:
            data = irc_socket.recv(2048).decode("UTF-8")
            for line in data.strip().split("\n"):
                self.console.info(line.strip())

            if "sasl authentication successful" in data.lower():
                self.irc_socket = irc_socket
                break

            if "sasl authentication failed" in data.lower():
                return False

        # Join the channel
        for channel in channels:
            irc_socket.send(bytes(f"JOIN {channel}\r\n", "UTF-8"))

        return irc_socket

    def main_irc_loop(self):
        """This is the main loop for IRC
        It handles the keep alive PING responses and the message relay
        """
        # Main bot loop
        while True:
            data = self.irc_socket.recv(2048).decode("UTF-8")

            # Respond to PING messages to keep the connection alive
            if data.startswith("PING"):
                self.irc_socket.send(bytes("PONG :pingis\n", "UTF-8"))
                self.console.info(f"Responded to PING from IRC: {data.strip()}")
                continue

            split_message = formatting.parse_irc_message(data)
            if split_message is None:
                continue

            for line in data.strip().split("\n"):
                self.console.info(line.strip())

            if not split_message["channel"].startswith("#"):
                continue

            if split_message["action"] == "PRIVMSG":
                asyncio.run_coroutine_threadsafe(
                    self.irc_cog.send_message_from_irc(split_message), self.loop
                )
            elif split_message["action"] == "MODE":
                asyncio.run_coroutine_threadsafe(
                    self.irc_cog.send_message_from_irc(split_message), self.loop
                )

    def format_message(self, message):
        """This formats the message from discord to prepare for sending to IRC
        Strips new lines and trailing white space

        Args:
            message (str): The string contents of the message

        Returns:
            str: The formatted message
        """
        permissions_prefix = self.get_permissions_prefix(message.author)
        message_str = f"{self.IRC_BOLD}[D]{self.IRC_BOLD} <{permissions_prefix}"
        message_str += f"{message.author}> {message.clean_content}"
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
        self.irc_socket.send(
            bytes(f"PRIVMSG {channel} :{formatted_message}\r\n", "UTF-8")
        )
