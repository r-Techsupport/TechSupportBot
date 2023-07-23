"""Module for defining the data bot methods."""

import urllib

import aiohttp
import expiringdict
import gino
import munch
from motor import motor_asyncio

from .extension import ExtensionsBot


class DataBot(ExtensionsBot):
    """Bot that supports Mongo and Postgres."""

    def __init__(self, *args, **kwargs):
        self.mongo = None
        self.db = None
        super().__init__(*args, **kwargs)
        self.http_cache = expiringdict.ExpiringDict(
            max_len=self.file_config.main.cache.http_cache_length,
            max_age_seconds=self.file_config.main.cache.http_cache_seconds,
        )

    def generate_db_url(self, postgres=True):
        """Dynamically converts config to a Postgres/MongoDB url.

        parameters:
            postgres (bool): True if the URL for Postgres should be retrieved
        """
        db_type = "postgres" if postgres else "mongodb"

        try:
            config_child = getattr(self.file_config.main, db_type)

            user = config_child.user
            password = config_child.password

            name = getattr(config_child, "name") if postgres else None

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
        await self.logger.debug("Obtaining and binding to Gino instance")

        db_ref = gino.Gino()
        db_url = self.generate_db_url()
        await db_ref.set_bind(db_url)

        db_ref.Model.__table_args__ = {"extend_existing": True}

        return db_ref

    def get_mongo_ref(self):
        """Grabs the MongoDB ref to the bot's configured table."""
        self.logger.console.debug("Obtaining MongoDB client")

        mongo_client = motor_asyncio.AsyncIOMotorClient(
            self.generate_db_url(postgres=False)
        )

        return mongo_client[self.file_config.main.mongodb.name]

    # pylint: disable=too-many-locals
    async def http_call(self, method, url, *args, **kwargs):
        """Makes an HTTP request.

        By default this returns JSON/dict with the status code injected.

        parameters:
            method (str): the HTTP method to use
            url (str): the URL to call
            use_cache (bool): True if the GET result should be grabbed from cache
            get_raw_response (bool): True if the actual response object should be returned
        """
        url = url.replace(" ", "%20").replace("+", "%2b")

        method = method.lower()
        use_cache = kwargs.pop("use_cache", False)
        get_raw_response = kwargs.pop("get_raw_response", False)

        cache_key = url.lower()
        if kwargs.get("params"):
            params = urllib.parse.urlencode(kwargs.get("params"))
            cache_key = f"{cache_key}?{params}"

        cached_response = (
            self.http_cache.get(cache_key) if (use_cache and method == "get") else None
        )

        client = None
        if cached_response:
            response_object = cached_response
            log_message = f"Retrieving cached HTTP GET response ({cache_key})"
        else:
            client = aiohttp.ClientSession()
            method_fn = getattr(client, method.lower())
            response_object = await method_fn(url, *args, **kwargs)
            if method == "get":
                self.http_cache[cache_key] = response_object
            log_message = f"Making HTTP {method.upper()} request to URL: {cache_key}"

        await self.logger.info(log_message)

        if get_raw_response:
            response = response_object
        else:
            response_json = await response_object.json()
            response = (
                munch.munchify(response_json) if response_object else munch.Munch()
            )
            response["status_code"] = getattr(response_object, "status", None)

        if client:
            await client.close()

        return response
