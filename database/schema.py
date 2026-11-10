"""Piccolo models for the existing database tables."""

import datetime

from piccolo.columns import Boolean, Serial, Timestamp, Varchar
from piccolo.conf.apps import table_finder
from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table


def bind_engine(engine: PostgresEngine) -> None:
    """Bind all tables defined in this schema to the database engine.

    Args:
        engine (PostgresEngine): The engine to use for this schema's tables
    """
    for table in table_finder([__name__], exclude_imported=True):
        table._meta.db = engine


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


class UserNote(Table, tablename="usernote"):
    """The postgres table for notes
    Currently used in who.py

    Attributes:
        pk (Serial): The primary key for this database
        user_id (Varchar): The user ID that has a note
        guild_id (Varchar): The guild ID that the note belongs to
        updated (Timestamp): The time the note was created on
        author_id (Varchar): The author of the note
        body (Varchar): The contents of the note
    """

    pk: Serial = Serial(primary_key=True)
    user_id: Varchar = Varchar(length=None, null=True, default=None)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    updated: Timestamp = Timestamp(
        null=True,
        default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
    )
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    body: Varchar = Varchar(length=None, null=True, default=None)
