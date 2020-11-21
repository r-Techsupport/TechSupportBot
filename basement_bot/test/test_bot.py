import aiounittest
import mock
from bot import BasementBot
from discord import Game
from utils.test import *


class TestBot(aiounittest.AsyncTestCase):
    @mock.patch("bot.BasementBot.start", return_value=None)
    @mock.patch("database.DatabaseAPI.__init__", return_value=None)
    @mock.patch("plugin.PluginAPI.__init__", return_value=None)
    @mock.patch("bot.BasementBot._load_config", return_value=get_mock_config())
    @mock.patch("discord.ext.commands.Bot.__init__", return_value=None)
    def test_init(
        self,
        _mock_bot,
        mock_load_config,
        mock_plugin_api,
        mock_database_api,
        mock_start,
    ):
        bbot = BasementBot(True)

        self.assertTrue(mock_load_config.called)
        self.assertEqual(bbot.game, "foo")
        self.assertTrue(mock_plugin_api.called)
        self.assertTrue(mock_database_api.called)
        self.assertTrue(mock_start.called)

    @mock.patch("bot.BasementBot.set_game")
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_on_ready(self, _mock_bot, mock_set_game):
        bbot = BasementBot(True)
        bbot.game = "foo"
        bbot.command_prefix = "."

        await bbot.on_ready()
        mock_set_game.assert_called_with("foo")

    @mock.patch("bot.BasementBot.change_presence")
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_set_game(self, _mock_bot, mock_change_presence):
        bbot = BasementBot(True)
        bbot.command_prefix = "."
        await bbot.set_game("foo")
        mock_change_presence.assert_called_with(activity=Game("foo"))

    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_start(self, _mock_bot):
        bbot = BasementBot(True)
        bbot.plugin_api = mock.MagicMock()
        bbot.loop = mock.MagicMock()
        bbot.start()
        self.assertTrue(bbot.plugin_api.load_plugins.called)
        self.assertTrue(bbot.loop.run_until_complete.called)

    @mock.patch("yaml.safe_load", return_value=get_mock_dict())
    @mock.patch("builtins.open", new_callable=mock.mock_open(read_data=""))
    @mock.patch("bot.BasementBot._validate_config", return_value=None)
    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_load_config(
        self, _mock_bot, mock_validate_config, _mock_file, _mock_safe_load
    ):
        bbot = BasementBot(True)
        config = bbot._load_config(True)

        self.assertTrue(mock_validate_config.called)
        self.assertEqual(config.main.required.auth_token, "foo")

    @mock.patch("bot.BasementBot.__init__", return_value=None)
    async def test_validate_config(self, _mock_bot):
        bbot = BasementBot(True)
        bbot.config = get_mock_config()

        bbot._validate_config()
        self.assertTrue("mock_plugin" in bbot.config.main.disabled_plugins)
        self.assertTrue("mock_plugin_2" in bbot.config.main.disabled_plugins)

        bbot.config.main.required.auth_token = None
        with self.assertRaises(ValueError):
            bbot._validate_config()
