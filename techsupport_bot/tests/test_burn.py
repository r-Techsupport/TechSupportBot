import munch
from extensions import BurnEmbed
import discord

def test_burnembed() -> None:
    embed = BurnEmbed(description="test")
    assert embed.title == "Burn Alert!"
    assert embed.color == discord.Color.red()
    assert embed.description == "test"