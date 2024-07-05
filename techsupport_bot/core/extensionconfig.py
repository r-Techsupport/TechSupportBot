"""This represents an extension config item when building in the setup function"""

from __future__ import annotations

from typing import Self

import munch


class ExtensionConfig:
    """Represents the config of an extension."""

    def __init__(self: Self) -> None:
        self.data = munch.DefaultMunch(None)

    def add(
        self: Self,
        key: str,
        datatype: str,
        title: str,
        description: str,
        default: str | bool | int | list[str] | list[int] | dict[str, str],
    ) -> None:
        """Adds a new entry to the config.

        This is usually used in the extensions's setup function.

        Args:
            key (str): the lookup key for the entry
            datatype (str): the datatype metadata for the entry
            title (str): the title of the entry
            description (str): the description of the entry
            default (str | bool | int | list[str] | list[int] | dict[str, str]):
                the default value to use for the config entry
        """
        self.data[key] = {
            "datatype": datatype,
            "title": title,
            "description": description,
            "default": default,
            "value": default,
        }
