This bot will use the Guild Members intent for the following reasons

moderation.events
    The bot monitors member who leave and join for logging purposes, supporting moderation efforts.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.members
    A command designed to enhance moderation efforts to get a yaml file of all members with a given role.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.modmail
    The bot monitors members who leave and join if they have an open thread in modmail to notify moderators that the user has left or joined.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.nickname
    The bot monitors members who join to enforce server nickname policies, modifying user nicknames to match our server rules should it be needed.

    This module does not send this information anywhere, nor does it store any information on disk.

moderation.notes
    The bot monitors members who join to determine if they have user notes set by our moderators. If so, upon re-joining our server, they are given the notes role.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

operation.forum
    The bot monitors members who leave to alert helpers in the thread the user has created that the individual who opened the thread has subsequently left the server.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.
