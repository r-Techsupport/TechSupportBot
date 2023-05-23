import asyncio
import imp
from functools import wraps

import discord
import mock
import munch
import pytest
import util
from discord.ext import commands
from mock import patch

# Patch function decorators before importing Burn
patch("util.with_typing", lambda x: x).start()
patch("discord.ext.commands.guild_only", return_value=None)
patch("discord.ext.commands.command", command=lambda f: f).start()

from extensions import Burn, BurnEmbed


def test_burnembed() -> None:
    embed = BurnEmbed(description="test")
    assert embed.title == "Burn Alert!"
    assert embed.color == discord.Color.red()
    assert embed.description == "test"


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_creation(asyncio_patch) -> None:
    test = Burn("1")

# This one needs some work, but I did the most annoying parts
@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_burn_command(self) -> None:
    test = Burn("1")
    ctx = "1"
    user_to_match = "1"
    test.burn(ctx, user_to_match=user_to_match)
    assert test.SEARCH_LIMIT == 50
