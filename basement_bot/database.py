"""Provides an interface for database sessions.
"""

from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from utils.helpers import get_env_value
from utils.logger import get_logger

log = get_logger("Database")


class DatabaseAPI:
    """API for accessing a database.

    parameters:
        bot (BasementBot): the bot object
        echo (bool): True for verbose logging
    """

    Table = declarative_base()

    def __init__(self, bot, echo=False):
        self.bot = bot
        self.db_string = self._get_db_string()
        log.debug(f"Connecting to DB: {self.db_string}")
        self.engine = create_engine(self.db_string, echo=echo)

    def get_session(self):
        """Creates a session instance.
        """
        return sessionmaker(bind=self.engine)()

    def create_table(self, table):
        """Wraps table creation.

        parameters:
            table (self.Table): the table class
        """
        try:
            log.debug(f"Attempting to create table {table.__name__}")
            table.__table__.create(self.engine, checkfirst=True)
        except InvalidRequestError:
            log.debug(f"Table {table.__name__} already exists - ignoring")

    @staticmethod
    def _get_db_string():
        """Gathers database environmental information.
        """
        user = get_env_value("DB_USER")
        name = get_env_value("DB_NAME")
        address = get_env_value("DB_ADDRESS")
        password = get_env_value("DB_PASSWORD")
        prefix = get_env_value("DB_PREFIX")
        return f"{prefix}://{user}:{password}@{address}/{name}"
