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
import os
from pathlib import Path
from typing import Any

import munch

BASE_PATH = "configuration/"


# Publically callable functions
def get_config_entry(guild_id: int, key: str) -> Any:  # noqa: ANN401
    """This searches for a guild specific config entry

    Args:
        guild_id (int): The ID of the guild
        key (str): The config key to look for

    Returns:
        Any: The value of the config, which may be of many types

    Raises:
        AttributeError: Raised if the passed key is not valid
    """

    if not _check_key_valid(key):
        raise AttributeError(f"Key {key} is invalid")

    default_entry = get_default_config_entry(key)

    if not _does_guild_config_exist(guild_id):
        return default_entry

    guild_config = _read_guild_json(guild_id)

    if key in guild_config:
        return guild_config[key]
    return default_entry


def get_default_config_entry(key: str) -> Any:  # noqa: ANN401
    """This gets the value from the default config file for the passed key

    Args:
        key (str): The key to search the config file for

    Returns:
        Any: The value from the default config file

    Raises:
        AttributeError: Raised if the passed key is not valid
    """
    if not _check_key_valid(key):
        raise AttributeError(f"Key {key} is invalid")

    default_config = _read_json_file("config.default.json")

    return default_config[key]


def get_default_config_json() -> munch.Munch:
    """This gets a munified versions of the default config file

    Returns:
        munch.Munch: The default configuration as defined
    """
    return _read_json_file("config.default.json")


def get_guild_config_json(guild_id: int) -> munch.Munch:
    """This gets a munified version of the guild config if it exists

    Args:
        guild_id (int): The guild ID to search for

    Raises:
        AttributeError: Raised if the specified guild has no config

    Returns:
        munch.Munch: The guild config read
    """
    if _does_guild_config_exist(guild_id):
        return _read_guild_json(guild_id)
    raise AttributeError(f"No config found for guild {guild_id}")


def write_guild_config_json(guild_id: int, new_config: munch.Munch) -> None:
    """A function to write a guild config with a munch.Munch json

    Args:
        guild_id (int): The ID of the guild to write to
        new_config (munch.Munch): The new config to write
    """
    _write_guild_json_file(guild_id, new_config)


def edit_config_entry(guild_id: int, key: str, new_value: Any) -> None:  # noqa: ANN401
    """This edits a config entry for a specific guild
    If there is no guild config for a given guild, a blank config is created

    Args:
        guild_id (int): The ID of the guild to change
        key (str): The key to write to the config
        new_value (Any): The value of the key to write

    Raises:
        AttributeError: Raised if the passed key is not valid
    """
    if not _check_key_valid(key):
        raise AttributeError(f"Key {key} is invalid")

    if not _does_guild_config_exist(guild_id):
        write_blank_guild_config(guild_id)

    guild_config = _read_guild_json(guild_id)
    guild_config[key] = new_value
    _write_guild_json_file(guild_id, guild_config)


def write_blank_guild_config(guild_id: int) -> None:
    """Creates a blank guild configuration file.

    Args:
        guild_id (int): The ID of the guild whose configuration should be created.
    """
    _write_guild_json_file(guild_id, munch.Munch(core_guild_id=guild_id))


# Internal functions only
def _check_key_valid(key: str) -> bool:
    """This will check if the key is valid and present in default config

    Args:
        key (str): The key to check for validity

    Returns:
        bool: True if the key exists, false if it doesn't
    """
    default_config = _read_json_file("config.default.json")

    if key in default_config:
        return True
    return False


def _does_guild_config_exist(guild_id: int) -> bool:
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


def _read_json_file(path: str) -> munch.Munch:
    """This reads a json file from disk and parses it into a munch.Munch
    This functions assumes the json file exists

    Args:
        path (str): The path of the json file to read

    Returns:
        munch.Munch: The read json file
    """
    with open(f"{BASE_PATH}{path}", encoding="utf-8") as file:
        return munch.munchify(json.load(file))


def _read_guild_json(guild_id: int) -> munch.Munch:
    """A function to get the json of a specific guild config

    Args:
        guild_id (int): The guild ID to get the config for

    Returns:
        munch.Munch: The munchified representation of the guild config
    """
    return _read_json_file(f"guild_configs/{guild_id}.json")


def _write_guild_json_file(guild_id: int, json_data: munch.Munch) -> None:
    """Writes a guild configuration file to disk.
    This will ensure the guild_configs folder exists as well

    Args:
        guild_id (int): The ID of the guild whose configuration should be written.
        json_data (munch.Munch): The configuration data to write.

    Raises:
        AttributeError: If the guild for the passed json data does not equal the passed guild_id
    """
    path = f"{BASE_PATH}/guild_configs/{guild_id}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if json_data.core_guild_id != guild_id:
        raise AttributeError("Guild config for incorrect guild")

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            munch.unmunchify(json_data),
            file,
            indent=4,
            ensure_ascii=False,
        )
