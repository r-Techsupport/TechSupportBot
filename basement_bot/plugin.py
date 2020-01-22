"""Module for plugin functions.
"""

import glob
import logging
import os
from os.path import basename, dirname, isfile, join

from discord.ext import commands


class PluginLoader:
    """Wrapper for plugin loading.

    parameters:
        bot (BasementBot): the bot object to which plugins are loading
    """

    def __init__(self, bot):
        self.bot = bot

    def load_plugins(self):
        """Adds functions as commands from the plugins directory.
        """
        for plugin in self._get_modules():
            logging.info(f"Loading plugin module {plugin}")

            try:
                self.bot.load_extension(plugin)

            except Exception as e:
                logging.error(f"Failed to load {plugin}: {e}")
            
    @staticmethod
    def _get_modules():
        """Gets the list of plugin modules.
        """
        files = glob.glob(f"{join(dirname(__file__))}/plugins/*.py")
        return [
            f"plugins.{basename(f)[:-3]}"
            for f in files
            if isfile(f) and not f.endswith("__init__.py")
        ]


# Utility functions


def get_api_key(name, raise_exception=True):
    """Grabs an API key from the environment and fails if nothing is found.

    parameters:
        name (str): the name of the environmental variable
        raise_exception (bool): True if an exception should be raised 
    """
    key = os.environ.get(name, None)
    if not key:
        if raise_exception:
            raise NameError(f"Unable to locate API key name {name}")
    return key


async def tagged_response(ctx, message):
    await ctx.send(f"{ctx.message.author.mention} {message}")
