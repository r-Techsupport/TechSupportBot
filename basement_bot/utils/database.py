"""Module for handling database interactions.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from logger import get_logger
from utils.helpers import get_env_value

log = get_logger("Database Handler")


class DatabaseHandler:
    """Wrapper for SQLAlchemy functions.
    """

    # pylint: disable=too-few-public-methods
    def __init__(self):

        db_string = self._get_db_string()
        log.debug(f"Connecting to DB: {db_string}")

        self.engine = create_engine(db_string, echo=True)
        self.Session = sessionmaker(bind=self.engine)
        self.Base = declarative_base()

    def initialize(self):
        """Wraps table creation.
        """
        self.Base.metadata.create_all(self.engine)

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
