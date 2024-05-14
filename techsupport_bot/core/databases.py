"""This file stores all of the postgres table declarations
All models can be used by any extension
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import gino.crud
import gino.declarative
import munch

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
        embed_config = bot.db.Column(bot.db.String, default="")
        hidden = bot.db.Column(bot.db.Boolean, default=False)
        protected = bot.db.Column(bot.db.Boolean, default=False)
        disabled = bot.db.Column(bot.db.Boolean, default=False)
        restricted = bot.db.Column(bot.db.Boolean, default=False)
        alias = bot.db.Column(bot.db.String, default="")

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
        guild_id = bot.db.Column(bot.db.String, default="")
        discord_channel_id = bot.db.Column(bot.db.String, default="")
        irc_channel_id = bot.db.Column(bot.db.String, default="")

    class ModmailBan(bot.db.Model):
        """The postgres table for modmail bans
        Currently used in modmail.py"""

        __tablename__ = "modmail_bans"
        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id = bot.db.Column(bot.db.String, default="")

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

    bot.models.Applications = Applications  # DONE
    bot.models.AppBans = ApplicationBans  # DONE
    bot.models.DuckUser = DuckUser  # DONE
    bot.models.Factoid = Factoid
    bot.models.FactoidJob = FactoidJob
    bot.models.Grab = Grab  # DONE
    bot.models.IRCChannelMapping = IRCChannelMapping  # DONE
    bot.models.ModmailBan = ModmailBan  # DONE
    bot.models.UserNote = UserNote  # DONE
    bot.models.Warning = Warning  # DONE
    bot.models.Config = Config  # DONE
    bot.models.Listener = Listener  # DONE
    bot.models.Rule = Rule  # DONE


# Internal functions


class NoDefault:
    pass


def convert_db_to_munch(entry: gino.crud.Model) -> munch.Munch:
    # We need to get the values from the database entry
    values_dict = entry.__values__
    # In order to remove the primary key, we need the table
    table = entry.__table__

    modified_dict = munch.Munch()

    # We must preserve the original since it's needed to make any modifications
    modified_dict["__original__"] = entry

    # Loop through all of the columns to ensure none of them are the primary key
    for column in table.columns:
        attr_name = column.name
        attr_value = values_dict[attr_name]
        modified_dict[attr_name] = attr_value

    return modified_dict


# Interaction functions


async def read_database(model: gino.declarative.ModelType) -> list[munch.Munch]:
    table = await model.query.gino.all()
    table_as_list: list[munch.Munch] = []
    for item in table:
        table_as_list.append(convert_db_to_munch(item))
    return table_as_list


async def delete_entry(entry: munch.Munch) -> None:
    if entry.__original__:
        await entry.__original__.delete()
    else:
        raise ValueError("Missing orignal key")


async def update_entry(entry: munch.Munch) -> munch.Munch:
    if not entry.__original__:
        raise ValueError("Missing orignal key")
    original_entry = entry.__original__

    update_kwargs = {}

    # Prepare key-value pairs for update
    for attr_name, attr_value in entry.items():
        if attr_name != "__original__":
            update_kwargs[attr_name] = attr_value

    # Apply the changes to the database
    await original_entry.update(**update_kwargs).apply()

    return convert_db_to_munch(original_entry)


def get_blank_entry(database: gino.declarative.ModelType) -> munch.Munch:
    table = database.__table__
    default_entry = munch.Munch()
    default_entry["__database__"] = database

    # We have to go through every column in the table
    for column in table.columns:
        if column.primary_key:
            continue
        # Set the default value to all columns that have one
        if column.default is None:
            # If no default value exists, make it a NoDefault class
            # This means the column is mandatory to fill out
            default_entry[column.name] = NoDefault()

    return default_entry


async def write_new_entry(entry: munch.Munch) -> munch.Munch:
    if not entry.__database__:
        raise ValueError("Missing database key")
    database = entry.__database__
    entry.pop("__database__")

    table_columns = {column.name for column in database.__table__.columns}
    entry_names = set(entry.keys())
    if not entry_names.issubset(table_columns):
        raise ValueError("Invalid keys detected")

    # Check if any entry values are of instance NoDefault
    for attr_name, attr_value in entry.items():
        if isinstance(attr_value, NoDefault):
            raise ValueError(
                f"Value for entry '{attr_name}' must be set before creation"
            )

    # Create a dictionary to store kwargs for creating a new database object
    create_kwargs = {}
    for attr_name, attr_value in entry.items():
        create_kwargs[attr_name] = attr_value

    # Create a new database object and apply the changes
    new_object = database(**create_kwargs)
    database_object = await new_object.create()
    return convert_db_to_munch(database_object)
