"""Piccolo models for the existing database tables."""

import datetime

from piccolo.columns import Boolean, Serial, Timestamp, Varchar
from piccolo.table import Table


class Grab(Table, tablename="grabs"):
    """An encrypted message saved by the Grab commands.

    Attributes:
        pk (Serial): The auto-incrementing primary key
        author_id (Varchar): The ID of the author of the original message
        channel (Varchar): The ID of the channel the message was grabbed from
        guild (Varchar): The ID of the guild the grab belongs to
        message (Varchar): The encrypted contents of the grabbed message
        message_hash (Varchar): The message hash used to identify duplicate grabs
        time (Timestamp): The UTC time the message was grabbed, without timezone information
        nsfw (Boolean): Whether the message was grabbed from an NSFW channel
    """

    pk: Serial = Serial(primary_key=True)
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    channel: Varchar = Varchar(length=None, null=True, default=None)
    guild: Varchar = Varchar(length=None, null=True, default=None)
    message: Varchar = Varchar(length=None, null=True, default=None)
    message_hash: Varchar = Varchar(length=None, null=True, default=None)
    time: Timestamp = Timestamp(
        null=True,
        default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
    )
    nsfw: Boolean = Boolean(null=True, default=False)
