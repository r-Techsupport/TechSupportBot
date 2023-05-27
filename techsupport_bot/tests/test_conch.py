import discord
import mock
import pytest
from extensions import MagicConch
from hypothesis import given
from hypothesis.strategies import text

from .helpers import MockBot


class FakeDiscordEnv:
    def __init__(self):
        self.bot = MockBot()
        self.conch = MagicConch(self.bot)


@given(text())
def test_format_question(question):
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        new_question = discord_env.conch.format_question(question)
        assert new_question.endswith("?")
        assert len(new_question) <= 256
        assert new_question[:-1] in question
        assert len(question) >= len(new_question) - 1


@mock.patch("asyncio.create_task", return_value=None)
def test_format_question_no_mark(_):
    discord_env = FakeDiscordEnv()
    new_question = discord_env.conch.format_question("This is a question")
    assert new_question == "This is a question?"


@mock.patch("asyncio.create_task", return_value=None)
def test_format_question_yes_mark(_):
    discord_env = FakeDiscordEnv()
    new_question = discord_env.conch.format_question("This is a question?")
    assert new_question == "This is a question?"


@given(text())
def test_generate_embed(question):
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        embed = discord_env.conch.generate_embed(question)
        assert embed.title == question
        assert embed.description in discord_env.conch.RESPONSES
        assert embed.thumbnail.url == discord_env.conch.PIC_URL
        assert embed.color == discord.Color.blurple()
