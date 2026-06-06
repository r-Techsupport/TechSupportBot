"""
Normal usage:
get_config_entry(guild, key)
get_default_config_entry(key)


/config commands:
get_json_config(guild)
update_json_config(guild, config_json)

Backend commands:
generate_blank_config_file()
check_key_valid(key)

"""

import json
from pathlib import Path
from typing import Any

import munch

BASE_PATH = "configuration/"


def get_config_entry(guild_id: int, key: str) -> Any:
    """This searches for a guild specific config entry

    Args:
        guild_id (int): The ID of the guild
        key (str): The config key to look for

    Returns:
        Any: The value of the config, which may be of many types
    """

    if not check_key_valid(key):
        raise AttributeError(f"Key {key} is invalid")

    default_entry = get_default_config_entry(key)

    if not does_guild_config_exist(guild_id):
        return default_entry

    guild_config = read_json_file(f"guild_configs/{guild_id}.json")

    if key in guild_config:
        return guild_config[key]
    return default_entry


def get_default_config_entry(key: str) -> Any:
    """This gets the value from the default config file for the passed key

    Args:
        key (str): The key to search the config file for

    Returns:
        Any: The value from the default config file
    """
    if not check_key_valid(key):
        raise AttributeError(f"Key {key} is invalid")

    default_config = read_json_file("config.default.json")

    return default_config[key]


# WORKING
def check_key_valid(key: str) -> bool:
    """This will check if the key is valid and present in default config

    Args:
        key (str): The key to check for validity

    Returns:
        bool: True if the key exists, false if it doesn't
    """
    default_config = read_json_file("config.default.json")

    if key in default_config:
        return True
    return False


def does_guild_config_exist(guild_id: int) -> bool:
    """This checks if a guild specific config file exists

    Args:
        guild_id (int): The ID of the guild to look for

    Returns:
        bool: True if exists, false if doesn't
    """
    path = Path(f"{BASE_PATH}guild_configs/{guild_id}.json")

    if path.exists():
        return True
    return False


def read_json_file(path: str) -> munch.Munch:
    """This reads a json file from disk and parses it into a munch.Munch
    This functions assumes the json file exists

    Args:
        path (str): The path of the json file to read

    Returns:
        munch.Munch: The read json file
    """
    with open(f"{BASE_PATH}{path}", encoding="utf-8") as file:
        return munch.munchify(json.load(file))
