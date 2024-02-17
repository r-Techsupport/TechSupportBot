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
        Currenty used in application.py"""

        __tablename__ = "applications"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        guild_id = bot.db.Column(bot.db.String)
        applicant_name = bot.db.Column(bot.db.String)
        applicant_id = bot.db.Column(bot.db.String)
        application_status = bot.db.Column(bot.db.String)
        background = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        application_time = bot.db.Column(
            bot.db.DateTime, default=datetime.datetime.utcnow
        )

    class ApplicationBans(bot.db.Model):
        """The postgres table for users banned from applications
        Currently used in application.py and who.py"""

        __tablename__ = "appbans"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        guild_id = bot.db.Column(bot.db.String)
        applicant_id = bot.db.Column(bot.db.String)

    class DuckUser(bot.db.Model):
        """The postgres table for ducks
        Currently used in duck.py"""

        __tablename__ = "duckusers"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        author_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        befriend_count = bot.db.Column(bot.db.Integer, default=0)
        kill_count = bot.db.Column(bot.db.Integer, default=0)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        speed_record = bot.db.Column(bot.db.Float, default=80.0)

    class Factoid(bot.db.Model):
        """The postgres table for factoids
        Currently used in factoid.py"""

        __tablename__ = "factoids"

        factoid_id = bot.db.Column(bot.db.Integer, primary_key=True)
        name = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        hidden = bot.db.Column(bot.db.Boolean, default=False)
        protected = bot.db.Column(bot.db.Boolean, default=False)
        disabled = bot.db.Column(bot.db.Boolean, default=False)
        restricted = bot.db.Column(bot.db.Boolean, default=False)
        alias = bot.db.Column(bot.db.String, default=None)

    class FactoidJob(bot.db.Model):
        """The postgres table for factoid loops
        Currently used in factoid.py"""

        __tablename__ = "factoid_jobs"

        job_id = bot.db.Column(bot.db.Integer, primary_key=True)
        factoid = bot.db.Column(
            bot.db.Integer, bot.db.ForeignKey("factoids.factoid_id")
        )
        channel = bot.db.Column(bot.db.String)
        cron = bot.db.Column(bot.db.String)

    class Grab(bot.db.Model):
        """The postgres table for grabs
        Currently used in grab.py"""

        __tablename__ = "grabs"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        author_id = bot.db.Column(bot.db.String)
        channel = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        nsfw = bot.db.Column(bot.db.Boolean, default=False)

    class IRCChannelMapping(bot.db.Model):
        """The postgres table for IRC->discord maps
        Currently used in relay.py"""

        __tablename__ = "ircchannelmap"
        map_id = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String, default=None)
        discord_channel_id = bot.db.Column(bot.db.String, default=None)
        irc_channel_id = bot.db.Column(bot.db.String, default=None)

    class ModmailBan(bot.db.Model):
        """The postgres table for modmail bans
        Currently used in modmail.py"""

        __tablename__ = "modmail_bans"
        user_id = bot.db.Column(bot.db.String, default=None, primary_key=True)

    class UserNote(bot.db.Model):
        """The postgres table for notes
        Currently used in who.py"""

        __tablename__ = "usernote"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        author_id = bot.db.Column(bot.db.String)
        body = bot.db.Column(bot.db.String)

    class Warning(bot.db.Model):
        """The postgres table for warnings
        Currently used in protect.py and who.py"""

        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    class Config(bot.db.Model):
        """The postgres table for guild config
        Currently used nearly everywhere"""

        __tablename__ = "guild_config"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String)
        config = bot.db.Column(bot.db.String)
        update_time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    class Listener(bot.db.Model):
        """The postgres table for listeners
        Currently used in listen.py"""

        __tablename__ = "listeners"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        src_id = bot.db.Column(bot.db.String)
        dst_id = bot.db.Column(bot.db.String)

    class Rule(bot.db.Model):
        """The postgres table for rules
        Currently used in rules.py"""

        __tablename__ = "guild_rules"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String)
        rules = bot.db.Column(bot.db.String)

    bot.models.Applications = Applications
    bot.models.AppBans = ApplicationBans
    bot.models.DuckUser = DuckUser
    bot.models.Factoid = Factoid
    bot.models.FactoidJob = FactoidJob
    bot.models.Grab = Grab
    bot.models.IRCChannelMapping = IRCChannelMapping
    bot.models.ModmailBan = ModmailBan
    bot.models.UserNote = UserNote
    bot.models.Warning = Warning
    bot.models.Config = Config
    bot.models.Listener = Listener
    bot.models.Rule = Rule
