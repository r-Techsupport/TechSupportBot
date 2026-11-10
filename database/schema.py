"""Piccolo models for the existing database tables."""

from piccolo.columns import Boolean, Integer, Serial, Timestamptz, Varchar
from piccolo.conf.apps import table_finder
from piccolo.constraints import Unique
from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table


def bind_engine(engine: PostgresEngine) -> None:
    """Bind all tables defined in this schema to the database engine.

    Args:
        engine (PostgresEngine): The engine to use for this schema's tables
    """
    for table in table_finder([__name__], exclude_imported=True):
        table._meta.db = engine  # pylint: disable=protected-access


class ApplicationBans(Table, tablename="appbans"):
    """The postgres table for users banned from applications

    Attributes:
        pk (Serial): The automatic primary key
        guild_id (Varchar): The string of the guild ID the applicant is banned in
        applicant_id (Varchar): The string representation of the ID of the user
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    applicant_id: Varchar = Varchar(length=None, null=True, default=None)


class Grab(Table, tablename="grabs"):
    """The table for the grab module, storing encrypted messages and who sent them.

    Attributes:
        pk (Serial): The auto-incrementing primary key
        author_id (Varchar): The ID of the author of the original message
        channel (Varchar): The ID of the channel the message was grabbed from
        guild (Varchar): The ID of the guild the grab belongs to
        message (Varchar): The encrypted contents of the grabbed message
        message_hash (Varchar): The message hash used to identify duplicate grabs
        time (Timestamptz): The UTC time the message was grabbed, without timezone information
        nsfw (Boolean): Whether the message was grabbed from an NSFW channel
    """

    pk: Serial = Serial(primary_key=True)
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    channel: Varchar = Varchar(length=None, null=True, default=None)
    guild: Varchar = Varchar(length=None, null=True, default=None)
    message: Varchar = Varchar(length=None, null=True, default=None)
    message_hash: Varchar = Varchar(length=None, null=True, default=None)
    time: Timestamptz = Timestamptz()
    nsfw: Boolean = Boolean(null=True, default=False)


class ModLog(Table, tablename="modlog"):
    """The postgres table for all mod log events

    Attributes:
        pk (Serial): The automatic primary key
        guild_id (Varchar): The string of the guild ID the user was banned in
        guild_case_id (Integer): The case number of the action taken
        action (Varchar): The string representation of the action taken
        reason (Varchar): The reason of the ban
        data (Varchar): Any extra data specific to the event logged
        moderator_id (Varchar): The ID of the moderator who banned
        member_id (Varchar): The ID of the user who was banned
        action_time (Timestamptz): The date and time of the ban
        until_time (Timestamptz): The time this action will expire
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None)
    guild_case_id: Integer = Integer()
    action: Varchar = Varchar(length=None)
    reason: Varchar = Varchar(length=None, null=True, default=None)
    data: Varchar = Varchar(length=None, null=True, default=None)
    moderator_id: Varchar = Varchar(length=None, null=True, default=None)
    member_id: Varchar = Varchar(length=None, null=True, default=None)
    action_time: Timestamptz = Timestamptz()
    until_time: Timestamptz = Timestamptz(null=True, default=None)

    unique_guild_case = Unique([guild_id, guild_case_id])


class ModmailBan(Table, tablename="modmail_bans"):
    """The postgres table for modmail bans.
    Currently used in modmail.py.

    Attributes:
        user_id (Varchar): The ID of the user banned from modmail.
    """

    user_id: Varchar = Varchar(length=None, primary_key=True)


class UserNote(Table, tablename="usernote"):
    """The table to store user notes, who set them and when

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
    updated: Timestamptz = Timestamptz()
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    body: Varchar = Varchar(length=None, null=True, default=None)


class XP(Table, tablename="user_xp"):
    """The table to store user XP per guild

    Attributes:
        pk (Serial): The primary key for the database
        guild_id (Varchar): The ID of the guild that the XP is for
        user_id (Varchar): The ID of the user
        xp (Integer): The amount of XP the user has
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    user_id: Varchar = Varchar(length=None, null=True, default=None)
    xp: Integer = Integer()
