"""Module for defining the data bot methods."""

import gino
from base import extension
from botlogging import LogLevel


class DataBot(extension.ExtensionsBot):
    """Bot that supports Postgres."""

    def __init__(self, *args, **kwargs):
        self.db = None
        super().__init__(*args, **kwargs)

    def generate_db_url(self):
        """Dynamically converts config to a Postgres url."""
        db_type = "postgres"

        try:
            config_child = getattr(self.file_config.database, db_type)

            user = config_child.user
            password = config_child.password

            name = getattr(config_child, "name")

            host = config_child.host
            port = config_child.port

        except AttributeError as exception:
            self.logger.console.warning(
                f"Could not generate DB URL for {db_type.upper()}: {exception}"
            )
            return None

        url = f"{db_type}://{user}:{password}@{host}:{port}"
        url_filtered = f"{db_type}://{user}:********@{host}:{port}"

        if name:
            url = f"{url}/{name}"

        # don't log the password
        self.logger.console.debug(f"Generated DB URL: {url_filtered}")

        return url

    async def get_postgres_ref(self):
        """Grabs the main DB reference.

        This doesn't follow a singleton pattern (use bot.db instead).
        """
        await self.logger.send_log(
            message="Obtaining and binding to Gino instance",
            level=LogLevel.DEBUG,
            console_only=True,
        )

        db_ref = gino.Gino()
        db_url = self.generate_db_url()
        await db_ref.set_bind(db_url)

        db_ref.Model.__table_args__ = {"extend_existing": True}

        return db_ref
