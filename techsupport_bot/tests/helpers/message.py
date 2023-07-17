"""
This is a file to store the fake discord.Message object
"""


class MockMessage:
    """
    This is the MockMessage class

    Currently implemented variables and methods:
    content -> The string containing the content of the message
    author -> The MockMember object who create the message
    clean_content -> The same as content
    attachments -> A list of MockAttacment objects
    """

    def __init__(self, content=None, author=None, attachments=None, reactions=None):
        self.content = content
        self.author = author
        self.clean_content = content
        self.attachments = attachments
        self.reactions = reactions

    async def add_reaction(self, reaction):
        """Replication of the adding a reaction
        Adding reactions to a previous message

        Args:
           reaction (list): An array of reactions on the message

        """
        self.reactions.append(reaction)
