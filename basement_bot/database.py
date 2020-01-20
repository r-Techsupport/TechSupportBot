import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class DatabaseHandler:
    """Wrapper for SQLAlchemy functions.
    """

    def __init__(self):

        env_info = self._get_env()
        db_string = f'postgres://admin:{env_info["password"]}@db/basement_bot'

        self.engine = create_engine(db_string, echo=True)
        self.Session = sessionmaker(bind=self.engine)
        self.Base = declarative_base()

    def initialize(self):
        """Wraps table creation.
        """
        self.Base.metadata.create_all(self.engine)

    @staticmethod
    def _get_env():
        """Gathers database environmental information.
        """
        data = {}
        password = os.environ.get("POSTGRES_PASSWORD")
        if not password:
            raise RuntimeError("Unable to get database password from environment")
        data["password"] = password

        return data
