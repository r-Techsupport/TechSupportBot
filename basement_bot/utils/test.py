"""Helpers for unit testing.
"""

import munch


def get_mock_dict():
    """Gets a mock config as a dict.
    """
    return {
        "main": {
            "required": {"auth_token": "foo", "command_prefix": "bar"},
            "optional": {"game": "foo"},
            "database": {
                "user": "bar",
                "password": "bar",
                "name": "bar",
                "host": "bar",
                "prefix": "bar",
                "port": 5432,
            },
            "disabled_plugins": [],
        },
        "plugins": {
            "mock_plugin": {"foo": "bar", "foo2": None},
            "mock_plugin_2": {"foo": {"foo": None}},
        },
    }


def get_mock_config():
    """Wraps the mock config as a Munch object.
    """
    return munch.munchify(get_mock_dict())
