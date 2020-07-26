import aiounittest
import mock
import sqlalchemy

import cogs


class TestBasicPlugin(aiounittest.AsyncTestCase):
    def test_type(self):
        self.assertEqual(cogs.BasicPlugin.PLUGIN_TYPE, "BASIC")

    def test_init(self):
        mock_bot = mock.MagicMock()
        plugin = cogs.BasicPlugin(mock_bot)
        self.assertEqual(plugin.bot, mock_bot)
        self.assertTrue(mock_bot.loop.create_task.called)


class TestMatchPlugin(aiounittest.AsyncTestCase):
    def test_type(self):
        self.assertEqual(cogs.MatchPlugin.PLUGIN_TYPE, "MATCH")

    @mock.patch("cogs.MatchPlugin.response", return_value=None)
    @mock.patch("cogs.MatchPlugin.match", return_value=True)
    async def test_on_message(self, mock_match, mock_response):
        mock_bot = mock.AsyncMock()
        mock_bot.user = 1
        plugin = cogs.MatchPlugin(mock_bot)

        # test just returns
        message = mock.AsyncMock()
        message.author = 1
        await plugin.on_message(message)
        self.assertTrue(not mock_bot.get_context.called)
        self.assertTrue(not mock_match.called)
        self.assertTrue(not mock_response.called)

        # test match
        mock_bot.reset_mock()
        mock_match.reset_mock()
        mock_response.reset_mock()
        message.author = 0
        await plugin.on_message(message)
        self.assertTrue(mock_bot.get_context.called)
        self.assertTrue(mock_match.called)
        self.assertTrue(mock_response.called)

        # test no match
        mock_bot.reset_mock()
        mock_match.reset_mock()
        mock_response.reset_mock()
        mock_match.return_value = False
        await plugin.on_message(message)
        self.assertTrue(mock_bot.get_context.called)
        self.assertTrue(mock_match.called)
        self.assertTrue(not mock_response.called)

    async def test_match(self):
        mock_bot = mock.AsyncMock()
        plugin = cogs.MatchPlugin(mock_bot)
        with self.assertRaises(RuntimeError):
            await plugin.match("foo", "bar")

    async def test_response(self):
        mock_bot = mock.AsyncMock()
        plugin = cogs.MatchPlugin(mock_bot)
        with self.assertRaises(RuntimeError):
            await plugin.response(object(), "foo")


class TestDatabasePlugin(aiounittest.AsyncTestCase):
    def test_type(self):
        self.assertEqual(cogs.DatabasePlugin.PLUGIN_TYPE, "DATABASE")

    def test_basetable(self):
        self.assertEqual(
            type(cogs.DatabasePlugin.BaseTable),
            type(sqlalchemy.ext.declarative.declarative_base()),
        )

    def test_init(self):
        mock_bot = mock.AsyncMock()
        model = mock.AsyncMock()
        plugin = cogs.DatabasePlugin(mock_bot, model)
        self.assertEqual(plugin.model, model)
        self.assertTrue(mock_bot.database_api.create_table.called)
        self.assertTrue(mock_bot.loop.create_task.called)
        self.assertEqual(plugin.db_session, mock_bot.database_api.get_session)


class TestLoopPlugin(aiounittest.AsyncTestCase):
    def test_type(self):
        self.assertEqual(cogs.LoopPlugin.PLUGIN_TYPE, "LOOP")

    def test_default_wait(self):
        self.assertTrue(isinstance(cogs.LoopPlugin.DEFAULT_WAIT, int))

    def test_init(self):
        mock_bot = mock.AsyncMock()
        plugin = cogs.LoopPlugin(mock_bot)
        self.assertEqual(plugin.bot, mock_bot)
        self.assertEqual(plugin.state, True)
        self.assertTrue(mock_bot.loop.create_task.called)

    @mock.patch("cogs.LoopPlugin.execute")
    @mock.patch("cogs.LoopPlugin.loop_preconfig")
    async def test_loop_execute(self, mock_loop_preconfig, mock_execute):
        mock_bot = mock.AsyncMock()
        plugin = cogs.LoopPlugin(mock_bot)
        wait_type = type(plugin.wait)

        async def wait_override(self):
            self.state = False
            self.called = True

        plugin.wait = wait_type(wait_override, plugin)
        await plugin._loop_execute()
        self.assertTrue(mock_loop_preconfig.called)
        self.assertTrue(mock_bot.loop.create_task.called)
        self.assertTrue(mock_execute.called)
        self.assertTrue(plugin.called)

    def test_cog_unload(self):
        mock_bot = mock.AsyncMock()
        plugin = cogs.LoopPlugin(mock_bot)
        plugin.cog_unload()
        self.assertEqual(plugin.state, False)

    @mock.patch("asyncio.sleep")
    async def test_wait(self, mock_sleep):
        mock_bot = mock.AsyncMock()
        plugin = cogs.LoopPlugin(mock_bot)
        await plugin.wait()
        self.assertTrue(mock_sleep.called)

    async def test_execute(self):
        mock_bot = mock.AsyncMock()
        plugin = cogs.LoopPlugin(mock_bot)
        with self.assertRaises(RuntimeError):
            await plugin.execute()
