import uuid
from random import choice

from cogs import BasicPlugin
from discord.ext import commands
from utils.helpers import tagged_response


def setup(bot):
    bot.add_cog(WouldYouRather(bot))


class Question:
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self.id = uuid.uuid4()

    def get_question(self):
        return f"Would you rather: {self.a} **OR** {self.b}?"


class WouldYouRather(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    async def preconfig(self):
        self.last = None

    QUESTIONS = [
        Question(
            "be able to eat anything you want and have it be perfect nutrition",
            "have to only sleep 1 hour a day and be fully rested",
        ),
        Question(
            "have an obsessive insane person love you",
            "have an obsessive insane person hate you",
        ),
        Question(
            "change sexes every time you sneeze",
            "not know the difference between a baby and a muffin",
        ),
        Question(
            "fuck the top half of Emma Watson's body with the bottom half of Hulk Hogan's body",
            "fuck the top half of Hulk Hogan's body with the bottom half of Emma Watson's body",
        ),
        Question("have hair for teeth", "have teeth for fair"),
        Question(
            "be very beautiful and have diarrhea forever",
            "very ugly and safe from diarrhea for the rest of your life",
        ),
        Question("chug 1 gallon of ketchup", "tongue-kiss a chimp for 5 minutes"),
        Question(
            "have 'All Star' by Smash Mouth play every time you orgasm",
            "orgasm every time 'All Star' by Smash Mouth plays",
        ),
        Question("be a feminine man", "be a masculine woman"),
        Question("feed the whole world forever", "cure all cancer forever"),
        Question(
            "have Cheeto dust on your fingers for a year",
            "have to walk around with wet socks for a year",
        ),
        Question(
            "give your parents unrestricted access to your browsing history",
            "your boss",
        ),
        Question(
            "have every song you hear slowly turn into 'All Star' by Smash Mouth",
            "have every movie you watch slowly turn into Shrek",
        ),
        Question(
            "have a cat with a human face",
            "have a dog with human hands instead of paws",
        ),
    ]

    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="wyr",
        brief="Gets a Would You Rather... question",
        description="Creates a random Would You Rather question",
        limitations="60 sec cooldown per guild",
    )
    async def wyr(self, ctx):
        while True:
            question = choice(self.QUESTIONS)
            if self.last != question.id:
                self.last = question.id
                break

        await tagged_response(ctx, question.get_question())
