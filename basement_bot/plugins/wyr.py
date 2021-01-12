import uuid
from random import choice

from cogs import BasicPlugin
from discord.ext import commands
from helper import with_typing


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
        Question("be a detective", "a pilot"),
        Question("go skiing", "go to a water park"),
        Question("fly a kite", "swing on a swing"),
        Question("dance", "sing"),
        Question("play hide and seek", "dodgeball"),
        Question("be incredibly funny", "incredibly smart"),
        Question("become five years older", "two years younger"),
        Question("have a full suit of armor", "a horse"),
        Question("be a master at drawing", "be an amazing singer"),
        Question("be a wizard", "a superhero"),
        Question("sail a boat", "ride in a hang glider"),
        Question("brush your teeth with soap", "drink sour milk"),
        Question("be a famous inventor", "a famous writer"),
        Question("do school work as a group", "by yourself"),
        Question("be able to do flips and backflips", "break dance"),
        Question("see a firework display", "a circus performance"),
        Question("it be warm and raining", "cold and snowing today"),
        Question("be able to create a new holiday", "create a new sport"),
        Question(
            "only be able to walk on all fours",
            "only be able to walk sideways like a crab",
        ),
        Question(
            "start a colony on another planet",
            "be the leader of a small country on Earth",
        ),
        Question(
            "be able to see things that are very far away, like binoculars",
            "be able to see things very close up, like a microscope",
        ),
        Question("be an incredibly fast swimmer", "an incredibly fast runner"),
        Question(
            "own an old-timey pirate ship and crew",
            "a private jet with a pilot and infinite fuel",
        ),
        Question(
            "be able to jump as far as a kangaroo",
            "hold your breath as long as a whale",
        ),
        Question("be able to type/text very fast", "be able to read really quickly"),
        Question(
            "randomly turn into a frog for a day once a month",
            "randomly turn into a bird for a day once every week",
        ),
        Question("have the chance to design a new toy", "create a new TV show"),
        Question("be really good at math", "really good at sports"),
        Question(
            "be the author of a popular book",
            "a musician in a band who released a popular album",
        ),
        Question(
            "live in a house shaped like a circle", "a house shaped like a triangle"
        ),
        Question(
            "live in a place with a lot of trees", "live in a place near the ocean"
        ),
        Question(
            "have your room redecorated however you want",
            "ten toys of your choice (can be any price)",
        ),
        Question("have a magic carpet that flies", "a see-through submarine"),
        Question(
            "everything in your house be one color",
            "every single wall and door be a different color",
        ),
        Question(
            "visit the international space station for a week",
            "stay in an underwater hotel for a week",
        ),
        Question(
            "have ninja-like skills", "have amazing coding skills in any language"
        ),
        Question("be able to control fire", "water"),
        Question(
            "have a new silly hat appear in your closet every morning",
            "a new pair of shoes appear in your closet once a week",
        ),
        Question(
            "be able to remember everything you’ve ever seen",
            "heard or be able to perfectly imitate any voice you heard",
        ),
        Question(
            "drink every meal as a smoothie",
            "never be able to eat food that has been cooked",
        ),
        Question("meet your favorite celebrity", "be on a TV show"),
        Question("be a master at origami", "a master of sleight of hand magic"),
        Question("have a tail that can’t grab things", "wings that can’t fly"),
        Question(
            "have a special room you could fill with as many bubbles as you want, anytime you want",
            "have a slide that goes from your roof to the ground",
        ),
        Question("dance in front of 1000 people", "sing in front of 1000 people"),
        Question("ride a very big horse", "a very small pony"),
        Question(
            "be able to shrink down to the size of an ant any time you wanted to",
            "be able to grow to the size of a two-story building anytime you wanted to",
        ),
        Question("be able to move silently", "have an incredibly loud and scary voice"),
        Question("be bulletproof", "be able to survive falls from any height"),
        Question("eat a whole raw onion", "a whole lemon"),
        Question(
            "be incredibly luck with average intelligence",
            "incredibly smart with average luck",
        ),
        Question(
            "be able to change color to camouflage yourself",
            "grow fifteen feet taller and shrink back down whenever you wanted",
        ),
        Question(
            "instantly become a grown up",
            "stay the age you are now for another two years",
        ),
        Question("have a personal life-sized robot", "a jetpack"),
        Question(
            "never have any homework", "be paid 10$ per hour for doing your homework"
        ),
        Question("take a coding class", "an art class"),
        Question(
            "eat a bowl of spaghetti noodles without sauce",
            "a bowl of spaghetti sauce without noodles",
        ),
        Question(
            "have eyes that change color depending on your mood",
            "hair that changes color depending on the temperature",
        ),
        Question("eat an apple", "an orange"),
        Question(
            "taste the best pizza that has ever existed once but never again",
            "have the 4th best pizza restaurant in the world within delivery distance",
        ),
        Question("go snorkeling on a reef", "camping by a lake"),
        Question("have an elephant-sized cat", "a cat-sized elephant"),
        Question(
            "be able to jump into any picture and instantly be in that place and time but able to return",
            "would you rather be able to take pictures of the future, just stand in a place think of a time in the future and take a picture",
        ),
        Question("play outdoors", "indoors"),
        Question("eat broccoli flavored ice cream", "meat flavored cookies"),
        Question(
            "eat one live nonpoisonous spider",
            "have fifty nonpoisonous spiders crawl on you all at once",
        ),
        Question("live on a sailboat", "in a cabin deep in the woods"),
        Question(
            "have an amazing tree house with slides and three rooms",
            "an amazing entertainment system with a huge TV and every game console",
        ),
        Question("eat a popsicle", "a cupcake"),
        Question("own a hot air balloon", "an airboat"),
        Question(
            "have a bubble gun that shoots giant 5-foot bubbles",
            "a bathtub-sized pile of Legos",
        ),
        Question("eat a worm", "a grasshopper"),
        Question("have super strength", "super speed"),
        Question("never eat cheese again", "never drink anything sweet again"),
        Question(
            "have your very own house next to your parent’s house",
            "live with your parents in a house that’s twice the size of the one you live in now",
        ),
        Question("have a cupcake", "a piece of cake"),
        Question(
            "be able to move wires around with your mind",
            "be able to turn any carpeted floor into a six-foot deep pool of water",
        ),
        Question(
            "be able to speak any language but not be able to read in any of them",
            "read any language but not be able to speak any of them",
        ),
        Question(
            "live in a house where all the walls were made of glass",
            "live in an underground house",
        ),
        Question("stay a kid until you turn 80", "instantly turn 40"),
        Question(
            "be able to watch any movies you want a week before they are released",
            "always know what will be trendy before it becomes a trend",
        ),
        Question("be an athlete in the Summer Olympics", "the Winter Olympics"),
        Question(
            "be fluent in 10 languages",
            "be able to code in 10 different programming languages",
        ),
        Question("drive a police car", "an ambulance"),
        Question(
            "have a piggy bank that doubles any money you put in it",
            "find ten dollars under your pillow every time you wake up",
        ),
        Question("own a mouse", "a rat"),
        Question("live in a cave", "a tree house"),
        Question("do a book report", "a science project for a school assignment"),
        Question("fly an airplane", "drive a fire truck"),
        Question("be a talented engineer", "a talented coder"),
        Question(
            "spend the whole day in a huge garden",
            "spend the whole day in a large museum",
        ),
        Question(
            "be able to find anything that was lost",
            "every time you touched someone they would be unable to lie",
        ),
        Question("be a babysitter", "a dog sitter"),
        Question("ride a bike", "ride a kick scooter"),
        Question(
            "work alone on a school project", "work with others on a school project"
        ),
        Question(
            "open one 5$ present every day",
            "one big present that costs between 100$ to 300$ once a month",
        ),
        Question(
            "have an unlimited supply of ice cream",
            "a popular ice cream flavor named after you",
        ),
        Question("live in a place that is always dusty", "always humid"),
        Question(
            "have any book you wanted for free",
            "be able to watch any movie you wanted for free",
        ),
        Question("be able to play the piano", "the guitar"),
        Question("be able to read lips", "know sign language"),
        Question("eat a hamburger", "a hot dog"),
        Question("ride a roller coaster", "see a movie"),
        Question(
            "be able to change the color of anything with just a thought",
            "know every language that has ever been spoken on Earth",
        ),
        Question("have super strong arms", "super strong legs"),
        Question("move to a different city", "move to a different country"),
        Question(
            "be wildly popular on the social media platform of your choice",
            "have an extremely popular podcast",
        ),
        Question(
            "be able to talk to animals and have them understand you, but you can’t understand them,",
            "would you rather be able to understand what animals say but they can’t understand you",
        ),
        Question("eat smores", "cupcakes"),
        Question("ride in a hang glider", "ride in a helicopter"),
        Question("never have to sleep", "never have to eat"),
        Question("be an amazing photographer", "an amazing writer"),
        Question(
            "sneeze uncontrollably for 15 minutes once every day",
            "sneeze once every 3 minutes of the day while you are awake",
        ),
        Question(
            "be able to remember everything in every book you read",
            "remember every conversation you have",
        ),
        Question("have 10 mosquito bites", "1 bee sting"),
        Question(
            "be an actor/actress in a movie",
            "write a movie script that would be made into a movie",
        ),
        Question("be able to talk to dogs", "cats"),
        Question("have a jetpack", "a jet"),
        Question("ride a roller coaster", "go down a giant water slide"),
        Question(
            "get every Lego set that comes out for free",
            "every new video game system that comes out for free",
        ),
        Question(
            "go on vacation to a new country every summer vacation",
            "get an extra three weeks of summer break",
        ),
        Question(
            "eat a turkey sandwich with vanilla ice cream inside",
            "eat vanilla ice cream with bits of turkey inside",
        ),
        Question("ride a skateboard", "a bike"),
        Question(
            "visit every country in the World", "be able to play any musical instrument"
        ),
        Question(
            "control the outcome of any coin flip",
            "be unbeatable at rock, paper, scissors",
        ),
        Question("be able to type faster than anyone", "speak faster than anyone"),
        Question("have a private movie theater", "your own private arcade"),
        Question("be a cyborg", "a robot"),
        Question("ride in a hang glider", "skydive"),
        Question(
            "every vegetable you eat taste like candy but still be healthy",
            "all water you drink taste like a different delicious beverage every time you drink it",
        ),
        Question(
            "be really good at skateboarding", "really good at any video game you tried"
        ),
        Question(
            "lay in a bathtub filled with worms for 5 minutes",
            "lay in a bathtub filled with beetles that don’t bite for 5 minutes",
        ),
        Question("live next to a theme park", "next to a zoo"),
        Question(
            "have a room with whiteboard walls that you can draw on",
            "a room where the whole ceiling is one big skylight",
        ),
        Question("have a house with trampoline floors", "a house with aquarium floors"),
        Question("live in a castle", "a spaceship traveling far from earth"),
        Question("play soccer", "baseball"),
        Question("ride a camel", "ride a horse"),
        Question(
            "be amazing at drawing and painting",
            "be able to remember everything you ever read",
        ),
        Question("have a jetpack", "a hoverboard that actually hovers (no wheels)"),
        Question("have a ten dollar bill", "ten dollars in coins"),
        Question("get up early", "stay up late"),
        Question(
            "be able to eat any spicy food without a problem",
            "never be bitten by another mosquito",
        ),
        Question(
            "never have to take a bath/shower but still always smell nice",
            "never have to get another shot but still be healthy",
        ),
        Question(
            "be able to learn everything in a book by putting it under your pillow while you slept",
            "be able to control your dreams every night",
        ),
        Question(
            "be able to see new colors that no other people could see",
            "be able to hear things that no other humans can hear",
        ),
        Question(
            "move to a country and city of your choice",
            "stay in your own country but not be able to decide where you moved",
        ),
        Question("have pancakes every day for breakfast", "pizza every day for dinner"),
        Question("drive a race car", "fly a helicopter"),
        Question(
            "be unable to control how fast you talk",
            "unable to control how loud you talk",
        ),
        Question(
            "be rich and unknown", "be famous and have enough money, but not be rich"
        ),
        Question(
            "live in a house in the forest where there aren’t many people around",
            "live in a city with lots of people around",
        ),
        Question("dance", "draw"),
        Question("have a 3d printer", "the best phone on the market"),
        Question("go snow skiing", "water skiing"),
        Question(
            "never be able to eat any type meat again",
            "never be able to eat things with sugar in them",
        ),
        Question("have no homework", "no tests"),
        Question(
            "be able to control the length of your hair with your mind",
            "be able to control the length of your fingernails with your mind",
        ),
        Question("get to name a newly discovered tree", "a newly discovered spider"),
        Question("swim in Jell-O", "swim in Nutella"),
        Question("play on swings", "play on a slide"),
        Question(
            "have the power to shrink things to half their size",
            "the power to enlarge things to twice their size",
        ),
        Question("live in a base under the ocean", "a floating base in the sky"),
        Question(
            "not need to eat and never be hungry",
            "not need to drink and never be thirsty",
        ),
        Question(
            "be the fastest kid at your school", "the smartest kid at your school"
        ),
        Question("be a scientist", "be the boss of a company"),
        Question(
            "have a magic freezer that always has all your favorite ice cream flavors",
            "one that has a different ice cream flavor every time you open the door",
        ),
        Question("have a very powerful telescope", "a very powerful microscope"),
        Question("hang out for an hour with 10 puppies", "10 kittens"),
        Question(
            "be able to change colors like a chameleon",
            "hold your breath underwater for an hour",
        ),
        Question("learn to surf", "learn to ride a skateboard"),
        Question(
            "eat your favorite food every day",
            "find 5 dollars under your pillow every morning",
        ),
        Question("have a pet penguin", "a pet Komodo dragon"),
        Question(
            "be able to eat pancakes as much as you want without it hurting your health",
            "be able to eat as much bacon as you want without it hurting your health",
        ),
        Question("be able to talk to animals", "be able to fly"),
        Question("own a restaurant", "be a chef"),
        Question("have a pet dinosaur of your choosing", "a dragon the size of a dog"),
        Question("have an amazing tree house", "your whole yard be a trampoline"),
        Question(
            "have a slide that goes from your home’s roof to the ground",
            "be able to change and control what color the lights are in your home",
        ),
        Question("be a famous musician", "a famous business owner"),
        Question("play in a giant mud puddle", "a pool"),
        Question(
            "have your favorite artist perform a private show just for you",
            "perform on stage next to your favorite artist for thousands of people",
        ),
        Question("be too hot", "too cold"),
        Question("have 100$ now", "1000$ in a year"),
        Question("have a real triceratops", "a robot triceratops"),
        Question(
            "have everything you draw become real", "become a superhero of your choice"
        ),
        Question(
            "be given every Lego set that was ever made",
            "get every new Lego set that comes out for free",
        ),
        Question("go to the beach", "go to the zoo"),
        Question("get a new pair of shoes", "a jacket"),
        Question("read a book", "read a magazine"),
        Question(
            "be the fastest swimmer on earth", "the third fastest runner on earth"
        ),
        Question("drink orange juice", "milk"),
        Question("go camping", "stay in a hotel room"),
        Question("go to the doctor for a shot", "the dentist to get a cavity filled"),
        Question(
            "be able to make plants grow very quickly",
            "be able to make it rain whenever you wanted",
        ),
        Question("be a falcon", "a dolphin"),
        Question("be able to read minds", "see one day into the future"),
        Question(
            "have fireworks go off every evening for an hour",
            "have Christmas three times a year",
        ),
        Question(
            "eat a bowl of spaghetti that was just one long noodle",
            "eat ice cream launched from a catapult",
        ),
        Question("watch a two-hour movie", "watch two hours of shows"),
    ]

    @with_typing
    @commands.cooldown(1, 30, commands.BucketType.guild)
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

        await self.bot.h.tagged_response(ctx, question.get_question())
