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

    bot.models.Applications = Applications
    bot.models.DuckUser = DuckUser  # Needs app command conversion
    bot.models.Votes = Votes
