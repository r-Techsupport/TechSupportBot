"""Piccolo models for the existing database tables."""

from piccolo.columns import (
    Boolean,
    DoublePrecision,
    ForeignKey,
    Integer,
    OnDelete,
    OnUpdate,
    Serial,
    Timestamptz,
    Varchar,
)
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


class Applications(Table, tablename="applications"):
    """The applications submitted by guild members.

    Attributes:
        pk (Serial): The automatic primary key
        guild_id (Varchar): The ID of the guild receiving the application
        applicant_name (Varchar): The applicant's name
        applicant_id (Varchar): The ID of the applicant
        application_status (Varchar): The current application status
        background (Varchar): The applicant's background answer
        reason (Varchar): The applicant's reason for applying
        application_time (Timestamptz): The timezone-aware UTC submission time
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    applicant_name: Varchar = Varchar(length=None, null=True, default=None)
    applicant_id: Varchar = Varchar(length=None, null=True, default=None)
    application_status: Varchar = Varchar(length=None, null=True, default=None)
    background: Varchar = Varchar(length=None, null=True, default=None)
    reason: Varchar = Varchar(length=None, null=True, default=None)
    application_time: Timestamptz = Timestamptz(null=True)


class DuckUser(Table, tablename="duckusers"):
    """A member's duck hunt scores and speed record within a guild.

    Attributes:
        pk (Serial): The automatic primary key
        author_id (Varchar): The ID of the member
        guild_id (Varchar): The ID of the guild
        befriend_count (Integer): The number of befriended ducks
        kill_count (Integer): The number of killed ducks
        updated (Timestamptz): The timezone-aware UTC time of the last hunt result
        speed_record (DoublePrecision): The fastest reaction time in seconds, or -1 if unset
    """

    pk: Serial = Serial(primary_key=True)
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    befriend_count: Integer = Integer(null=True, default=0)
    kill_count: Integer = Integer(null=True, default=0)
    updated: Timestamptz = Timestamptz(null=True)
    speed_record: DoublePrecision = DoublePrecision(null=True, default=-1.0)


class FactoidData(Table, tablename="factoid_data"):
    """The content, presentation settings and usage of a factoid.

    Attributes:
        factoid_data_id (Serial): The factoid's automatic primary key
        guild (Varchar): The ID of the guild the factoid belongs to
        message (Varchar): The plaintext message
        create_time (Timestamptz): The timezone-aware creation time in UTC
        edit_time (Timestamptz): The timezone-aware last edit time in UTC
        json_string (Varchar): The serialized embed JSON
        flags (Integer): The bitwise property flags
        times_called (Integer): The number of times the factoid has been called
    """

    factoid_data_id: Serial = Serial(primary_key=True)
    guild: Varchar = Varchar(length=None, null=True, default=None, index=True)
    message: Varchar = Varchar(length=None, null=True, default=None)
    create_time: Timestamptz = Timestamptz(null=True)
    edit_time: Timestamptz = Timestamptz(null=True)
    json_string: Varchar = Varchar(length=None, null=True, default=None)
    flags: Integer = Integer(null=True, default=0)
    times_called: Integer = Integer(null=True, default=0)


class FactoidCall(Table, tablename="factoid_calls"):
    """An alias pointing to a factoid's content.

    Attributes:
        factoid_call_id (Serial): The alias's automatic primary key
        guild (Varchar): The ID of the guild the alias belongs to
        name (Varchar): The alias used to invoke the factoid
        factoid_data_id (ForeignKey): The referenced factoid data ID
        unique_guild_name (Unique): Prevents duplicate alias names within a guild
    """

    factoid_call_id: Serial = Serial(primary_key=True)
    guild: Varchar = Varchar(length=None, null=True, default=None, index=True)
    name: Varchar = Varchar(length=None, null=True, default=None, index=True)
    factoid_data_id: ForeignKey = ForeignKey(
        FactoidData,
        target_column=FactoidData.factoid_data_id,
        null=False,
        index=True,
        on_delete=OnDelete.no_action,
        on_update=OnUpdate.no_action,
    )

    unique_guild_name: Unique = Unique([guild, name])


class FactoidJob(Table, tablename="factoid_jobs"):
    """A scheduled factoid invocation for a channel.

    Attributes:
        factoid_job_id (Serial): The job's automatic primary key
        guild (Varchar): The ID of the guild the job belongs to
        factoid_data_id (ForeignKey): The referenced factoid data ID
        channel (Varchar): The ID of the channel to send the factoid in
        cron (Varchar): The cron expression controlling the schedule
    """

    factoid_job_id: Serial = Serial(primary_key=True)
    guild: Varchar = Varchar(length=None, null=True, default=None, index=True)
    factoid_data_id: ForeignKey = ForeignKey(
        FactoidData,
        target_column=FactoidData.factoid_data_id,
        null=False,
        index=True,
        on_delete=OnDelete.no_action,
        on_update=OnUpdate.no_action,
    )
    channel: Varchar = Varchar(length=None, null=True, default=None)
    cron: Varchar = Varchar(length=None, null=True, default=None)


class FeatureBan(Table, tablename="featurebans"):
    """The postgres table for users banned from various features

    Attributes:
        pk (Serial): The automatic primary key
        guild_id (Varchar): The string of the guild ID the user is banned in
        user_id (Varchar): The string of the ID of the user who is banned
        ban_flags (Integer): A bitwise set of flags for features this user is banned from
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    user_id: Varchar = Varchar(length=None, null=True, default=None)
    ban_flags: Integer = Integer(default=0)


class Grab(Table, tablename="grabs"):
    """The table for the grab module, storing encrypted messages and who sent them.

    Attributes:
        pk (Serial): The auto-incrementing primary key
        author_id (Varchar): The ID of the author of the original message
        channel (Varchar): The ID of the channel the message was grabbed from
        guild (Varchar): The ID of the guild the grab belongs to
        message (Varchar): The encrypted contents of the grabbed message
        message_hash (Varchar): The message hash used to identify duplicate grabs
        time (Timestamptz): The timezone-aware UTC time the message was grabbed
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


class IRCChannelMapping(Table, tablename="ircchannelmap"):
    """The channel mappings between Discord and IRC.

    Attributes:
        map_id (Serial): The automatic primary key
        guild_id (Varchar): The ID of the guild containing the Discord channel
        discord_channel_id (Varchar): The ID of the Discord channel
        irc_channel_id (Varchar): The name of the IRC channel
    """

    map_id: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    discord_channel_id: Varchar = Varchar(length=None, null=True, default=None)
    irc_channel_id: Varchar = Varchar(length=None, null=True, default=None)


class Listener(Table, tablename="listeners"):
    """A message forwarding registration between two channels.

    Attributes:
        pk (Serial): The automatic primary key
        src_id (Varchar): The ID of the source channel
        dst_id (Varchar): The ID of the destination channel
    """

    pk: Serial = Serial(primary_key=True)
    src_id: Varchar = Varchar(length=None, null=True, default=None)
    dst_id: Varchar = Varchar(length=None, null=True, default=None)


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
        unique_guild_case (Unique): Prevents duplicate case numbers within a guild
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

    unique_guild_case: Unique = Unique([guild_id, guild_case_id])


class ModmailBan(Table, tablename="modmail_bans"):
    """The postgres table for modmail bans.
    Currently used in modmail.py.

    Attributes:
        user_id (Varchar): The ID of the user banned from modmail.
    """

    user_id: Varchar = Varchar(length=None, primary_key=True)


class Rule(Table, tablename="guild_rules"):
    """The postgres table for guild rules.

    Attributes:
        pk (Serial): The automatic primary key
        guild_id (Varchar): The ID of the guild these rules belong to
        rules (Varchar): The JSON representation of the rules
    """

    pk: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    rules: Varchar = Varchar(length=None, null=True, default=None)


class UserNote(Table, tablename="usernote"):
    """The table to store user notes, who set them and when

    Attributes:
        pk (Serial): The primary key for this database
        user_id (Varchar): The user ID that has a note
        guild_id (Varchar): The guild ID that the note belongs to
        updated (Timestamptz): The timezone-aware time the note was created on
        author_id (Varchar): The author of the note
        body (Varchar): The contents of the note
    """

    pk: Serial = Serial(primary_key=True)
    user_id: Varchar = Varchar(length=None, null=True, default=None)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    updated: Timestamptz = Timestamptz()
    author_id: Varchar = Varchar(length=None, null=True, default=None)
    body: Varchar = Varchar(length=None, null=True, default=None)


class Votes(Table, tablename="voting"):
    """The postgres table for votes
    Currently used in voting.py

    Attributes:
        vote_id (Serial): The primary key of the vote
        guild_id (Varchar): The guild the vote belongs to
        message_id (Varchar): The ID of the message the vote is in
        thread_id (Varchar): The ID of the thread the vote is in
        vote_owner_id (Varchar): The ID of the user who started the vote
        vote_description (Varchar): The long form description of the vote
        vote_ids_yes (Varchar): The comma separated list of who has voted yes
        vote_ids_no (Varchar): The comma separated list of who has voted no
        vote_ids_abstain (Varchar): The comma separated list of who have abstained
        vote_ids_all (Varchar): The comma separated list of who has voted
        vote_ids_eligible (Varchar): The comma separated list of all who can vote
        votes_yes (Integer): The number of votes for yes
        votes_no (Integer): The number of votes for no
        votes_abstain (Integer): The number of votes that have abstained
        start_time (Timestamptz): The start time of the vote
        vote_active (Boolean): If the vote is current active or not
        blind (Boolean): If the vote needs to be blind
        anonymous (Boolean): If the vote needs to be anonymous
    """

    vote_id: Serial = Serial(primary_key=True)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    message_id: Varchar = Varchar(length=None, null=True, default=None)
    thread_id: Varchar = Varchar(length=None, null=True, default=None)
    vote_owner_id: Varchar = Varchar(length=None, null=True, default=None)
    vote_description: Varchar = Varchar(length=None, null=True, default=None)
    vote_ids_yes: Varchar = Varchar(length=None, null=True, default="")
    vote_ids_no: Varchar = Varchar(length=None, null=True, default="")
    vote_ids_abstain: Varchar = Varchar(length=None, null=True, default="")
    vote_ids_all: Varchar = Varchar(length=None, null=True, default="")
    vote_ids_eligible: Varchar = Varchar(length=None, null=True, default="")
    votes_yes: Integer = Integer(null=True, default=0)
    votes_no: Integer = Integer(null=True, default=0)
    votes_abstain: Integer = Integer(null=True, default=0)
    start_time: Timestamptz = Timestamptz(null=True)
    vote_active: Boolean = Boolean(null=True, default=True)
    blind: Boolean = Boolean(null=True, default=False)
    anonymous: Boolean = Boolean(null=True, default=False)


class Warning(Table, tablename="warnings"):
    """The postgres table for moderator warnings.

    Attributes:
        pk (Serial): The automatic primary key
        user_id (Varchar): The ID of the user who received the warning
        guild_id (Varchar): The ID of the guild where the warning was given
        reason (Varchar): The reason for the warning
        time (Timestamptz): The timezone-aware UTC time the warning was given
        invoker_id (Varchar): The ID of the moderator who gave the warning
    """

    pk: Serial = Serial(primary_key=True)
    user_id: Varchar = Varchar(length=None, null=True, default=None)
    guild_id: Varchar = Varchar(length=None, null=True, default=None)
    reason: Varchar = Varchar(length=None, null=True, default=None)
    time: Timestamptz = Timestamptz(null=True)
    invoker_id: Varchar = Varchar(length=None, null=True, default=None)


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
