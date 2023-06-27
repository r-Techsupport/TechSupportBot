"""
This is a file to store the fake discord.Member object
"""


class MockMember:
    """
    This is the MockMember class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the fake user
    bot -> Boolean stating if this member is a bot or not
    mention -> String that is just <@ID>
    name -> The string containing the users username
    display_avatar -> The MockAsset object for the avatar
    """

    def __init__(self, id=None, bot=False, name=None, display_avatar=None):
        self.id = id
        self.bot = bot
        self.mention = f"<@{id}>"
        self.name = name
        self.display_avatar = display_avatar
