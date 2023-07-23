"""Module for defining the data bot methods."""

import time
import urllib
from collections import deque
from urllib.parse import urlparse

import aiohttp
import expiringdict
import gino
import munch
from error import HTTPRateLimit
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
        self.url_rate_limit_history = {}
        # Rate limit configurations for each root URL
        # This is "URL": (calls, seconds)
        self.rate_limits = {
            "api.urbandictionary.com": (2, 60),
            "api.openai.com": (3, 60),
            "www.googleapis.com": (5, 60),
            "ipinfo.io": (1, 30),
            "api.open-notify.org": (1, 60),
            "geocode.xyz": (1, 60),
            "v2.jokeapi.dev": (1, 60),
            "api.kanye.rest": (1, 60),
            "newsapi.org": (1, 30),
            "accounts.spotify.com": (3, 60),
            "api.spotify.com": (3, 60),
            "api.mymemory.translated.net": (1, 60),
            "api.openweathermap.org": (3, 60),
            "api.wolframalpha.com": (3, 60),
            "xkcd.com": (5, 60),
            "api.github.com": (3, 60),
            "api.giphy.com": (3, 60),
            "strawpoll.com": (3, 60),
        }
        # For the variable APIs, if they don't exist, don't rate limit them
        try:
            self.rate_limits[urlparse(self.file_config.main.api_url.dumpdbg).netloc] = (
                1,
                60,
            )
        except AttributeError:
            self.logger.warning("No dumpdbg API URL found. Not rate limiting dumpdbg")
        try:
            self.rate_limits[urlparse(self.file_config.main.api_url.linx).netloc] = (
                20,
                60,
            )
        except AttributeError:
            self.logger.warning("No linx API URL found. Not rate limiting linx")

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

    async def http_call(self, method, url, *args, **kwargs):
        """Makes an HTTP request.

        By default this returns JSON/dict with the status code injected.

        parameters:
            method (str): the HTTP method to use
            url (str): the URL to call
            use_cache (bool): True if the GET result should be grabbed from cache
            get_raw_response (bool): True if the actual response object should be returned
        """
        # Get the URL not the endpoint being called
        ignore_rate_limit = False
        root_url = urlparse(url).netloc

        # If the URL is not rate limited, we assume it can be executed an unlimited amount of times
        if root_url in self.rate_limits:
            executions_allowed, time_window = self.rate_limits[root_url]

            now = time.time()

            # If the URL being called is not in the history, add it
            # A deque allows easy max limit length
            if root_url not in self.url_rate_limit_history:
                self.url_rate_limit_history[root_url] = deque(
                    [], maxlen=executions_allowed
                )

            # Determine which calls, if any, have to be removed because they are out of the time
            while (
                self.url_rate_limit_history[root_url]
                and now - self.url_rate_limit_history[root_url][0] >= time_window
            ):
                self.url_rate_limit_history[root_url].popleft()

            # Determind if we hit or exceed the limit, and we should observe the limit
            if (
                not ignore_rate_limit
                and len(self.url_rate_limit_history[root_url]) >= executions_allowed
            ):
                time_to_wait = time_window - (
                    now - self.url_rate_limit_history[root_url][0]
                )
                time_to_wait = max(time_to_wait, 0)
                raise HTTPRateLimit(time_to_wait)

            # Add an entry for this call with the timestamp the call was placed
            self.url_rate_limit_history[root_url].append(now)

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
