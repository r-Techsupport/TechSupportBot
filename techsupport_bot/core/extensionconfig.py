"""This represents an extension config item when building in the setup function"""
import munch


class ExtensionConfig:
    """Represents the config of an extension."""

    def __init__(self):
        self.data = munch.DefaultMunch(None)

    def add(self, key, datatype, title, description, default):
        """Adds a new entry to the config.

        This is usually used in the extensions's setup function.

        parameters:
            key (str): the lookup key for the entry
            datatype (str): the datatype metadata for the entry
            title (str): the title of the entry
            description (str): the description of the entry
            default (Any): the default value to use for the entry
        """
        self.data[key] = {
            "datatype": datatype,
            "title": title,
            "description": description,
            "default": default,
            "value": default,
        }
