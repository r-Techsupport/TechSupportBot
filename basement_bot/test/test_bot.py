import aiounittest
import mock
from discord import Game

from bot import BasementBot


class TestBot(aiounittest.AsyncTestCase):
    @mock.patch("database.DatabaseAPI.__init__", return_value=None)
    @mock.patch("plugin.PluginAPI.__init__", return_value=None)
    @mock.patch("discord.ext.commands.Bot.__init__", return_value=None)
    def test_init(self, _mock_bot, mock_plugin_api, mock_database_api):
        bbot = BasementBot("foo", game="bar")
        self.assertEqual(bbot.game, "bar")
        self.assertTrue(mock_plugin_api.called)
        self.assertTrue(mock_database_api.called)

    @mock.patch("bot.BasementBot.set_game")
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_on_ready(self, _mock_bot, mock_set_game):
        bbot = BasementBot("foo", game="bar")
        bbot.game = "bar"
        bbot.command_prefix = "."
        await bbot.on_ready()
        mock_set_game.assert_called_with("bar")

    @mock.patch("bot.BasementBot.change_presence")
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_set_game(self, _mock_bot, mock_change_presence):
        bbot = BasementBot("foo", game="bar")
        bbot.command_prefix = "."
        await bbot.set_game("foo")
        mock_change_presence.assert_called_with(activity=Game("foo"))

    @mock.patch("discord.ext.commands.Bot.start",)
    @mock.patch("discord.ext.commands.Bot.__init__", return_value=None)
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_start(self, _mock_bot, _mock_super, mock_start):
        bbot = BasementBot("foo", game="bar")
        bbot.plugin_api = mock.MagicMock()
        await bbot.start()
        self.assertTrue(bbot.plugin_api.load_plugins.called)
        self.assertTrue(mock_start.called)

    @mock.patch("discord.ext.commands.Bot.logout",)
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_shutdown(self, _mock_bot, mock_logout):
        bbot = BasementBot("foo", game="bar")
        await bbot.shutdown()
        self.assertTrue(mock_logout.called)
