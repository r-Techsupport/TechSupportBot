import aiounittest
import mock

import utils.helpers


class TestHelpers(aiounittest.AsyncTestCase):
    @mock.patch("os.environ.get", return_value="bar")
    def test_get_env_value(self, mock_get):
        # test normal get
        value = utils.helpers.get_env_value("foo")
        self.assertEqual(value, "bar")

        mock_get.return_value = None
        # test exception raise
        with self.assertRaises(NameError):
            value = utils.helpers.get_env_value("foo")

        # test exception pass
        value = utils.helpers.get_env_value("foo", raise_exception=False)
        self.assertEqual(value, None)

    async def test_tagged_response(self):
        context = mock.AsyncMock()
        await utils.helpers.tagged_response(context, "hello world")
        self.assertTrue(context.send.called)

    async def test_emoji_reaction(self):
        context = mock.AsyncMock()
        emoji = "foo"
        await utils.helpers.emoji_reaction(context, emoji)
        self.assertTrue(context.message.add_reaction.called)

    async def test_priv_response(self):
        context = mock.AsyncMock()
        await utils.helpers.priv_response(context, "hello world")
        self.assertTrue(context.message.author.create_dm.called)

    @mock.patch("utils.helpers.priv_response")
    async def test_is_admin(self, mock_priv_response):
        # test normal admin
        context = mock.AsyncMock()
        context.message.author.id = 67890
        context.bot.config.main.admins.ids = ["12345", "67890"]
        permission = await utils.helpers.is_admin(context)
        self.assertEqual(permission, True)

        # test not admin
        context.message.author.id = 00000
        permission = await utils.helpers.is_admin(context)
        self.assertTrue(mock_priv_response.called)
        self.assertEqual(permission, False)

        # test empty admin list
        context.bot.config.main.admins.ids = []
        context.message.author.id = 67890
        permission = await utils.helpers.is_admin(context)
        self.assertEqual(permission, False)
