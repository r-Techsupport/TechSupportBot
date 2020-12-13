"""Helper class for making safer embeds."""
from discord import Embed


class SafeEmbed(Embed):
    """Wraps embed creation to avoid 400 errors when sending."""

    def add_field(self, *, name, value, inline=True):
        """Wraps the default add_field method with argument length checks.

        parameters:
            name (str): the name of the field
            value (str): the value of the field
            inline (bool): True if the field should be inlined with the last field
        """

        # if the value cannot be stringified, it is not valid
        try:
            value = str(value)
        except Exception:
            value = ""

        if len(name) > 256:
            name = name[:256]
        if len(value) > 256:
            value = value[:256]

        return super().add_field(name=name, value=value, inline=inline)
