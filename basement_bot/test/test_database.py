import aiounittest
import mock

from database import DatabaseAPI
from utils.test import get_mock_config


class TestDatabase(aiounittest.AsyncTestCase):
    @mock.patch("database.create_engine", return_value=0)
    @mock.patch("database.DatabaseAPI._get_db_string", return_value="foo")
    def test_init(self, _mock_get_db_string, _mock_create_engine):
        mock_bot = mock.MagicMock()
        api = DatabaseAPI(mock_bot)
        self.assertEqual(api.bot, mock_bot)
        self.assertEqual(api.db_string, "foo")
        self.assertEqual(api.engine, 0)

    @mock.patch("database.DatabaseAPI.__init__", return_value=None)
    @mock.patch("database.sessionmaker", return_value=lambda: 0)
    def test_get_session(self, _mock_sessionmaker, _mock_init):
        mock_bot = mock.MagicMock()
        api = DatabaseAPI(mock_bot)
        api.engine = mock.MagicMock()
        session = api.get_session()
        self.assertEqual(session, 0)

    @mock.patch("database.DatabaseAPI.__init__", return_value=None)
    def test_create_table(self, _mock_init):
        mock_bot = mock.MagicMock()
        api = DatabaseAPI(mock_bot)
        api.engine = mock.MagicMock()
        table = mock.MagicMock()
        table.__name__ = "foo"
        table.__table__ = mock.MagicMock()
        api.create_table(table)
        self.assertTrue(table.__table__.create)

    @mock.patch("database.DatabaseAPI.__init__", return_value=None)
    def test_get_db_string(self, _mock_init):
        mock_bot = mock.MagicMock()
        mock_bot.config = get_mock_config()

        api = DatabaseAPI(bot=mock_bot)
        api.bot = mock_bot
        db_string = api._get_db_string()
        self.assertEqual(db_string, "bar://bar:bar@bar:5432/bar")
