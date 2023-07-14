import asyncio
import base64
import socket


class IRC:
    irc_socket = None
    irc_cog = None
    loop = None

    def __init__(self, loop):
        self.loop = loop

    def connect_irc(
        self, server: str, port: int, channels: list, name: str, password: str
    ):
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
            print(data)

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
        # IRC server information
        bot_nickname = "TSDevBot"

        # Main bot loop
        while True:
            data = self.irc_socket.recv(2048).decode("UTF-8")
            print(data)

            # Respond to PING messages to keep the connection alive
            if data.startswith("PING"):
                self.irc_socket.send(bytes("PONG :pingis\n", "UTF-8"))

            channel_start = data.find("PRIVMSG") + len("PRIVMSG") + 1
            channel_end = data.find(":", channel_start)
            channel = data[channel_start:channel_end].strip()
            if not channel.startswith("#"):
                continue

            asyncio.run_coroutine_threadsafe(
                self.irc_cog.send_message_from_irc(data, channel), self.loop
            )

    def format_message(self, message):
        message = message.replace("\n", " ")
        return message.strip()

    def send_message_from_discord(self, message, channel):
        formatted_message = self.format_message(message)
        self.irc_socket.send(
            bytes(f"PRIVMSG {channel} :{formatted_message}\r\n", "UTF-8")
        )
