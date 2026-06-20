"""This file stores all of the postgres table declarations
All models can be used by any extension
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bot


def setup_models(bot: bot.TechSupportBot) -> None:
    """A function to setup all of the postgres tables
    This is stored in bot.models variable

    Args:
        bot (bot.TechSupportBot): The bot object to register the databases to
    """

    class Applications(bot.db.Model):
        """The postgres table for applications
        Currenty used in application.py

        Attributes:
            pk (int): The automatic primary key
            guild_id (str): The string of the guild ID the application is in
            applicant_name (str): The name of the user who submitted the app
            applicant_id (str): The string representation of the ID of the user
            application_status (str): The string representation of the status
            background (str): The answer to the background question of the application
            reason (str): The answer to the reason question of the application
            application_time (datetime.datetime): The time the application was submitted
        """

        __tablename__ = "applications"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        guild_id: str = bot.db.Column(bot.db.String)
        applicant_name: str = bot.db.Column(bot.db.String)
        applicant_id: str = bot.db.Column(bot.db.String)
        application_status: str = bot.db.Column(bot.db.String)
        background: str = bot.db.Column(bot.db.String)
        reason: str = bot.db.Column(bot.db.String)
        application_time: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )

    class ApplicationBans(bot.db.Model):
        """The postgres table for users banned from applications
        Currently used in application.py and who.py

        Attributes:
            pk (int): The automatic primary key
            guild_id (str): The string of the guild ID the applicant is banned in
            applicant_id (str): The string representation of the ID of the user
        """

        __tablename__ = "appbans"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        guild_id: str = bot.db.Column(bot.db.String)
        applicant_id: str = bot.db.Column(bot.db.String)

    class ModLog(bot.db.Model):
        """The postgres table for banlogs
        Currently used in modlog.py

        Attributes:
            __tablename__ (str): The name of the table in postgres
            pk (int): The automatic primary key
            guild_id (str): The string of the guild ID the user was banned in
            guild_case_id (int): The case number of the action taken
            action (str): The string representation of the action taken
            reason (str): The reason of the ban
            data (str): Any extra data specific to the event logged
            moderator_id (str): The ID of the moderator who banned
            member_id (str): The ID of the user who was banned
            action_time (datetime): The date and time of the ban
            until_time (datetime): The time this action will expire
        """

        __tablename__ = "modlog"
        __table_args__ = (bot.db.UniqueConstraint("guild_id", "guild_case_id"),)

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        guild_id = bot.db.Column(bot.db.String)
        guild_case_id = bot.db.Column(bot.db.Integer)
        action = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String, default="")
        data = bot.db.Column(bot.db.String, default="")
        moderator_id = bot.db.Column(bot.db.String, default="")
        member_id = bot.db.Column(bot.db.String, default="")
        action_time = bot.db.Column(
            bot.db.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
        until_time = bot.db.Column(
            bot.db.DateTime(timezone=True),
            nullable=True,
        )

    class DuckUser(bot.db.Model):
        """The postgres table for ducks
        Currently used in duck.py

        Attributes:
            pk (int): The automatic primary key
            author_id (str): The string representation of the ID of the user
            guild_id (str): The string of the guild ID the duckuser has participated in
            befriend_count (int): The amount of ducks the user has befriended
            kill_count (int): The amount of ducks the user has killed
            updated (datetime.datetime): The last time the duck user interacted with a duck
            speed_record (float): The fastest this user has killed or friended a duck
        """

        __tablename__ = "duckusers"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        author_id: str = bot.db.Column(bot.db.String)
        guild_id: str = bot.db.Column(bot.db.String)
        befriend_count: int = bot.db.Column(bot.db.Integer, default=0)
        kill_count: int = bot.db.Column(bot.db.Integer, default=0)
        updated: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )
        speed_record: float = bot.db.Column(bot.db.Float, default=-1.0)

    class FactoidData(bot.db.Model):
        __tablename__ = "factoid_data"

        factoid_data_id: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild: str = bot.db.Column(bot.db.String, index=True)
        message: str = bot.db.Column(bot.db.String)
        create_time: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )
        edit_time: datetime.datetime = bot.db.Column(
            bot.db.DateTime,
            default=datetime.datetime.utcnow,
        )
        json_string: str = bot.db.Column(bot.db.String, default=None)
        flags: int = bot.db.Column(bot.db.Integer, default=0)
        times_called: int = bot.db.Column(bot.db.Integer, default=0)

    class FactoidCall(bot.db.Model):
        __tablename__ = "factoid_calls"

        factoid_call_id: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild: str = bot.db.Column(bot.db.String, index=True)
        name: str = bot.db.Column(bot.db.String, index=True)

        factoid_data_id = bot.db.Column(
            bot.db.Integer,
            bot.db.ForeignKey("factoid_data.factoid_data_id"),
            nullable=False,
            index=True,
        )

    class FactoidJob(bot.db.Model):
        __tablename__ = "factoid_jobs"

        factoid_job_id: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild: str = bot.db.Column(bot.db.String, index=True)
        factoid_data_id = bot.db.Column(
            bot.db.Integer,
            bot.db.ForeignKey("factoid_data.factoid_data_id"),
            nullable=False,
            index=True,
        )

        channel: str = bot.db.Column(bot.db.String)
        cron: str = bot.db.Column(bot.db.String)

    class Grab(bot.db.Model):
        """The postgres table for grabs
        Currently used in grab.py

        Attributes:
            pk (int): The primary key for this database
            author_id (str): The ID of the author of the original grab message
            channel (str): The channel the message was grabbed from
            guild (str): The guild the message was grabbed from
            message (str): The string contents of the message
            message_hash (str): A hash of the contents of the message
            time (datetime.datetime): The time the message was grabbed
            nsfw (bool): Whether the message was grabbed in an NSFW channel
        """

        __tablename__ = "grabs"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True)
        author_id: str = bot.db.Column(bot.db.String)
        channel: str = bot.db.Column(bot.db.String)
        guild: str = bot.db.Column(bot.db.String)
        message: str = bot.db.Column(bot.db.String)
        message_hash: str = bot.db.Column(bot.db.String)
        time: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )
        nsfw: bool = bot.db.Column(bot.db.Boolean, default=False)

    class IRCChannelMapping(bot.db.Model):
        """The postgres table for IRC->discord maps
        Currently used in relay.py

        Attributes:
            map_id (int): The primary key for the database
            guild_id (str): The guild where the discord channel exists at
            discord_channel_id (str): The ID of the discord channel
            irc_channel_id (str): The name of the IRC channel
        """

        __tablename__ = "ircchannelmap"

        map_id: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id: str = bot.db.Column(bot.db.String, default=None)
        discord_channel_id: str = bot.db.Column(bot.db.String, default=None)
        irc_channel_id: str = bot.db.Column(bot.db.String, default=None)

    class ModmailBan(bot.db.Model):
        """The postgres table for modmail bans
        Currently used in modmail.py

        Attributes:
            user_id (str): The ID of the user banned from modmail
        """

        __tablename__ = "modmail_bans"

        user_id: str = bot.db.Column(bot.db.String, default=None, primary_key=True)

    class UserNote(bot.db.Model):
        """The postgres table for notes
        Currently used in who.py

        Attributes:
            pk (int): The primary key for this database
            user_id (str): The user ID that has a note
            guild_id (str): The guild ID that the note belongs to
            updated (datetime.datetime): The time the note was created on
            author_id (str): The author of the note
            body (str): The contents of the note
        """

        __tablename__ = "usernote"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id: str = bot.db.Column(bot.db.String)
        guild_id: str = bot.db.Column(bot.db.String)
        updated: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )
        author_id: str = bot.db.Column(bot.db.String)
        body: str = bot.db.Column(bot.db.String)

    class Warning(bot.db.Model):
        """The postgres table for warnings
        Currently used in protect.py and who.py

        Attributes:
            __tablename__ (str): The name of the table in postgres
            pk (int): The primary key for the database
            user_id (str): The user who got warned
            guild_id (str): The guild this warn occured in
            reason (str): The reason for the warn
            time (datetime): The time the warning was given
            invoker_id (str): The moderator who made the warning
        """

        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        invoker_id = bot.db.Column(bot.db.String)

    class Listener(bot.db.Model):
        """The postgres table for listeners
        Currently used in listen.py

        Attributes:
            pk (int): The primary key for the database
            src_id (str): The source channel for the listener
            dst_id (str): The destination channel for the listener
        """

        __tablename__ = "listeners"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True)
        src_id: str = bot.db.Column(bot.db.String)
        dst_id: str = bot.db.Column(bot.db.String)

    class Rule(bot.db.Model):
        """The postgres table for rules
        Currently used in rules.py

        Attributes:
            pk (int): The primary key for the database
            guild_id (str): The ID of the guild that these rules are for
            rules (str): The json representation of the rules
        """

        __tablename__ = "guild_rules"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id: str = bot.db.Column(bot.db.String)
        rules: str = bot.db.Column(bot.db.String)

    class Votes(bot.db.Model):
        """The postgres table for votes
        Currently used in voting.py

        Attributes:
            vote_id (int): The primary key of the vote
            guild_id (str): The guild the vote belongs to
            message_id (str): The ID of the message the vote is in
            thread_id (str): The ID of the thread the vote is in
            vote_owner_id (str): The ID of the user who started the vote
            vote_description (str): The long form description of the vote
            vote_ids_yes (str): The comma separated list of who has voted yes
            vote_ids_no (str): The comma separated list of who has voted no
            vote_ids_abstain (str): The comma separated list of who have abstained
            vote_ids_all (str): The comma separated list of who has voted
            vote_ids_eligible (str): The comma separated list of all who can vote
            votes_yes (int): The number of votes for yes
            votes_no (int): The number of votes for no
            votes_abstain (int): The number of votes that have abstained
            start_time (datetime.datetime): The start time of the vote
            vote_active (bool): If the vote is current active or not
            blind (bool): If the vote needs to be blind
            anonymous (bool): If the vote needs to be anonymous
        """

        __tablename__ = "voting"

        vote_id: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id: str = bot.db.Column(bot.db.String)
        message_id: str = bot.db.Column(bot.db.String)
        thread_id: str = bot.db.Column(bot.db.String)
        vote_owner_id: str = bot.db.Column(bot.db.String)
        vote_description: str = bot.db.Column(bot.db.String)
        vote_ids_yes: str = bot.db.Column(bot.db.String, default="")
        vote_ids_no: str = bot.db.Column(bot.db.String, default="")
        vote_ids_abstain: str = bot.db.Column(bot.db.String, default="")
        vote_ids_all: str = bot.db.Column(bot.db.String, default="")
        vote_ids_eligible: str = bot.db.Column(bot.db.String, default="")
        votes_yes: int = bot.db.Column(bot.db.Integer, default=0)
        votes_no: int = bot.db.Column(bot.db.Integer, default=0)
        votes_abstain: int = bot.db.Column(bot.db.Integer, default=0)
        start_time: datetime.datetime = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )
        vote_active: bool = bot.db.Column(bot.db.Boolean, default=True)
        blind: bool = bot.db.Column(bot.db.Boolean, default=False)
        anonymous: bool = bot.db.Column(bot.db.Boolean, default=False)

    class XP(bot.db.Model):
        """The postgres table for XP
        Currently used in xp.py

        Attributes:
            pk (int): The primary key for the database
            guild_id (str): The ID of the guild that the XP is for
            user_id (str): The ID of the user
            xp (int): The amount of XP the user has
        """

        __tablename__ = "user_xp"

        pk: int = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id: str = bot.db.Column(bot.db.String)
        user_id: str = bot.db.Column(bot.db.String)
        xp: int = bot.db.Column(bot.db.Integer)

    bot.models.Applications = Applications
    bot.models.AppBans = ApplicationBans
    bot.models.ModLog = ModLog
    bot.models.DuckUser = DuckUser
    bot.models.FactoidData = FactoidData
    bot.models.FactoidCall = FactoidCall
    bot.models.FactoidJob = FactoidJob
    bot.models.Grab = Grab
    bot.models.IRCChannelMapping = IRCChannelMapping
    bot.models.ModmailBan = ModmailBan
    bot.models.UserNote = UserNote
    bot.models.Warning = Warning
    bot.models.Listener = Listener
    bot.models.Rule = Rule
    bot.models.Votes = Votes
    bot.models.XP = XP
