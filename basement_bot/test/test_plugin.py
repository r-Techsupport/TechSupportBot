import aiounittest
import mock

from plugin import PluginAPI


class TestPlugin(aiounittest.AsyncTestCase):

    TEST_MODULES = ["/foo/bar/test1.py", "/foo/bar/test2.py", "/foo/bar/__init__.py"]

    def test_init(self):
        mock_bot = mock.MagicMock()
        api = PluginAPI(mock_bot)
        self.assertEqual(api.bot, mock_bot)
        self.assertEqual(api.plugins, {})

    @mock.patch("plugin.isfile", return_value=True)
    @mock.patch("glob.glob", return_value=TEST_MODULES)
    def test_get_modules(self, _mock_glob, _mock_isfile):
        mock_bot = mock.MagicMock()
        api = PluginAPI(mock_bot)
        modules = api.get_modules()
        self.assertTrue("test1" in modules)
        self.assertTrue("test2" in modules)
        self.assertTrue("__init__" not in modules)

    def test_load_plugin(self):
        mock_bot = mock.MagicMock()

        # test normal loading
        api = PluginAPI(mock_bot)
        response = api.load_plugin("foo")
        self.assertEqual(response.status, True)
        self.assertEqual(response.message, f"Successfully loaded `foo`")
        self.assertTrue(mock_bot.load_extension.called)
        self.assertEqual(api.plugins["foo"], {"status": "loaded", "memory": {}})

        # test already loaded
        mock_bot = mock.MagicMock()
        api = PluginAPI(mock_bot)
        api.plugins["foo"] = {"status": "loaded", "memory": {}}
        response = api.load_plugin("foo")
        self.assertEqual(response.status, False)
        self.assertEqual(response.message, "Plugin `foo` already loaded - ignoring")
        self.assertTrue(not mock_bot.load_extension.called)

        # test exception passing
        mock_bot = mock.MagicMock()
        mock_bot.load_extension.side_effect = OSError
        api = PluginAPI(mock_bot)
        response = api.load_plugin("foo")
        self.assertEqual(response.status, False)
        self.assertEqual(response.message, "Failed to load `foo`: ")

        # test exception raising
        with self.assertRaises(RuntimeError):
            api = PluginAPI(mock_bot)
            response = api.load_plugin("foo", False)

    def test_unload_plugin(self):
        mock_bot = mock.MagicMock()

        # test already unloaded
        api = PluginAPI(mock_bot)
        response = api.unload_plugin("foo")
        self.assertEqual(response.status, False)
        self.assertEqual(response.message, "Plugin `foo` not loaded - ignoring")

        # test normal unloading
        mock_bot = mock.MagicMock()
        api = PluginAPI(mock_bot)
        api.plugins["foo"] = {"status": "loaded"}
        response = api.unload_plugin("foo")
        self.assertEqual(response.status, True)
        self.assertEqual(response.message, "Successfully unloaded `foo`")
        self.assertTrue(mock_bot.unload_extension.called)
        self.assertEqual(api.plugins.get("foo"), None)

        # test exception passing
        mock_bot = mock.MagicMock()
        mock_bot.unload_extension.side_effect = OSError
        api = PluginAPI(mock_bot)
        api.plugins["foo"] = {"status": "loaded"}
        response = api.unload_plugin("foo")
        self.assertEqual(response.status, False)
        self.assertEqual(response.message, "Failed to unload `foo`: ")

        # test exception raising
        with self.assertRaises(RuntimeError):
            api = PluginAPI(mock_bot)
            api.plugins["foo"] = {"status": "loaded"}
            response = api.unload_plugin("foo", False)

    @mock.patch("plugin.PluginAPI.load_plugin")
    @mock.patch("plugin.isfile", return_value=True)
    @mock.patch("glob.glob", return_value=TEST_MODULES)
    def test_load_plugins(self, _mock_glob, _mock_isfile, mock_load_plugin):
        mock_bot = mock.MagicMock()
        api = PluginAPI(mock_bot)
        api.load_plugins()
        self.assertTrue(mock_load_plugin.called)
