import asyncio
import datetime
import functools
import random

import base
import discord
import embeds
import util
from discord import Color as embed_colors
from discord.ext import commands


def setup(bot):
    class DuckUser(bot.db.Model):
        __tablename__ = "duckusers"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        author_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        befriend_count = bot.db.Column(bot.db.Integer, default=0)
        kill_count = bot.db.Column(bot.db.Integer, default=0)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.ExtensionConfig()
    config.add(
        key="hunt_channels",
        datatype="list",
        title="DuckHunt Channel IDs",
        description="The IDs of the channels the duck should appear in",
        default=[],
    )
    config.add(
        key="min_wait",
        datatype="int",
        title="Min wait (hours)",
        description="The minimum number of hours to wait between duck events",
        default=2,
    )
    config.add(
        key="max_wait",
        datatype="int",
        title="Max wait (hours)",
        description="The maximum number of hours to wait between duck events",
        default=4,
    )
    config.add(
        key="timeout",
        datatype="int",
        title="Duck timeout (seconds)",
        description="The amount of time before the duck disappears",
        default=60,
    )
    config.add(
        key="cooldown",
        datatype="int",
        title="Duck cooldown (seconds)",
        description="The amount of time to wait between bef/bang messages",
        default=5,
    )
    config.add(
        key="success_rate",
        datatype="int",
        title="Success rate (percent %)",
        description="The success rate of bef/bang messages",
        default=50,
    )

    bot.add_cog(DuckHunt(bot=bot, models=[DuckUser], extension_name="duck"))
    bot.add_extension_config("duck", config)


# I don't know why I did this
MW2_QUOTES = [
    {
        "message": "Never in the field of human conflict was so much owed by so many to so few.",
        "author": "Winston Churchill",
    },
    {
        "message": "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "author": "Winston Churchill",
    },
    {
        "message": "In war there is no prize for the runner-up.",
        "author": "General Omar Bradley",
    },
    {
        "message": "Ours is a world of nuclear giants and ethical infants. We know more about war than we know about peace, more about killing than we know about living.",
        "author": "General Omar Bradley",
    },
    {
        "message": "The soldier above all others prays for peace, for it is the soldier who must suffer and bear the deepest wounds and scars of war.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "They died hard, those savage men - like wounded wolves at bay. They were filthy, and they were lousy, and they stunk. And I loved them.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "We must be prepared to make heroic sacrifices for the cause of peace that we make ungrudgingly for the cause of war. There is no task that is more important or closer to my heart.",
        "author": "Albert Einstein",
    },
    {
        "message": "War is an ugly thing, but not the ugliest of things. The decayed and degraded state of moral and patriotic feeling which thinks that nothing is worth war is much worse. The person who has nothing for which he is willing to fight, nothing which is more important than his own personal safety, is a miserable creature, and has no chance of being free unless made or kept so by the exertions of better men than himself.",
        "author": "John Stuart Mill",
    },
    {
        "message": "Future years will never know the seething hell and the black infernal background, the countless minor scenes and interiors of the secession war; and it is best they should not. The real war will never get in the books.",
        "author": "Walt Whitman",
    },
    {
        "message": "There's no honorable way to kill, no gentle way to destroy. There is nothing good in war. Except its ending.",
        "author": "Abraham Lincoln",
    },
    {
        "message": "The death of one man is a tragedy. The death of millions is a statistic.",
        "author": "Joseph Stalin",
    },
    {
        "message": "Death solves all problems - no man, no problem.",
        "author": "Joseph Stalin",
    },
    {
        "message": "In the Soviet army it takes more courage to retreat than advance.",
        "author": "Joseph Stalin",
    },
    {
        "message": "It is foolish and wrong to mourn the men who died. Rather we should thank God that such men lived.",
        "author": "General George S. Patton",
    },
    {
        "message": "Never think that war, no matter how necessary, nor how justified, is not a crime.",
        "author": "Ernest Hemingway",
    },
    {
        "message": "Every man's life ends the same way. It is only the details of how he lived and how he died that distinguish one man from another.",
        "author": "Ernest Hemingway",
    },
    {
        "message": "All wars are civil wars, because all men are brothers.",
        "author": "Francois Fenelon",
    },
    {
        "message": "I have never advocated war except as a means of peace.",
        "author": "Ulysses S. Grant",
    },
    {
        "message": "Older men declare war. But it is the youth that must fight and die.",
        "author": "Herbert Hoover",
    },
    {"message": "Only the dead have seen the end of war.", "author": "Plato"},
    {
        "message": "Death is nothing, but to live defeated and inglorious is to die daily.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "It is well that war is so terrible, or we should get too fond of it.",
        "author": "Robert E. Lee",
    },
    {
        "message": "A soldier will fight long and hard for a bit of colored ribbon.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "He who fears being conquered is sure of defeat.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "You must not fight too often with one enemy, or you will teach him all your art of war.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "There's a graveyard in northern France where all the dead boys from D-Day are buried. The white crosses reach from one horizon to the other. I remember looking it over and thinking it was a forest of graves. But the rows were like this, dizzying, diagonal, perfectly straight, so after all it wasn't a forest but an orchard of graves. Nothing to do with nature, unless you count human nature.",
        "author": "Barbara Kingsolver",
    },
    {"message": "If we don't end war, war will end us.", "author": "H. G. Wells"},
    {
        "message": "From my rotting body, flowers shall grow and I am in them and that is eternity.",
        "author": "Edvard Munch",
    },
    {
        "message": "He who has a thousand friends has not a friend to spare, And he who has one enemy will meet him everywhere.",
        "author": "Ali ibn-Abi-Talib",
    },
    {
        "message": "For the Angel of Death spread his wings on the blast, And breathed in the face of the foe as he pass'd; And the eyes of the sleepers wax'd deadly and chill, And their hearts but once heaved, and for ever grew still!",
        "author": "George Gordon Byron, The Destruction of Sennacherib",
    },
    {
        "message": "They wrote in the old days that it is sweet and fitting to die for one's country. But in modern war, there is nothing sweet nor fitting in your dying. You will die like a dog for no good reason.",
        "author": "Ernest Hemingway",
    },
    {
        "message": "There is many a boy here today who looks on war as all glory, but, boys, it is all hell. You can bear this warning voice to generations yet to come. I look upon war with horror.",
        "author": "General William Tecumseh Sherman",
    },
    {
        "message": "War is as much a punishment to the punisher as it is to the sufferer.",
        "author": "Thomas Jefferson",
    },
    {
        "message": "War would end if the dead could return.",
        "author": "Stanley Baldwin",
    },
    {
        "message": "When you have to kill a man it costs nothing to be polite.",
        "author": "Winston Churchill",
    },
    {
        "message": "Battles are won by slaughter and maneuver. The greater the general, the more he contributes in maneuver, the less he demands in slaughter.",
        "author": "Winston Churchill",
    },
    {
        "message": "History will be kind to me for I intend to write it.",
        "author": "Winston Churchill",
    },
    {
        "message": "We shall defend our island, whatever the cost may be, we shall fight on the beaches, we shall fight on the landing grounds, we shall fight in the fields and in the streets, we shall fight in the hills; we shall never surrender.",
        "author": "Winston Churchill",
    },
    {
        "message": "When you get to the end of your rope, tie a knot and hang on.",
        "author": "Franklin D. Roosevelt",
    },
    {
        "message": "A hero is no braver than an ordinary man, but he is brave five minutes longer.",
        "author": "Ralph Waldo Emerson",
    },
    {
        "message": "Our greatest glory is not in never failing, but in rising up every time we fail.",
        "author": "Ralph Waldo Emerson",
    },
    {
        "message": "The characteristic of a genuine heroism is its persistency. All men have wandering impulses, fits and starts of generosity. But when you have resolved to be great, abide by yourself, and do not weakly try to reconcile yourself with the world. The heroic cannot be the common, nor the common the heroic.",
        "author": "Ralph Waldo Emerson",
    },
    {
        "message": "If the opposition disarms, well and good. If it refuses to disarm, we shall disarm it ourselves.",
        "author": "Joseph Stalin",
    },
    {
        "message": "The object of war is not to die for your country but to make the other bastard die for his.",
        "author": "General George S. Patton",
    },
    {
        "message": "Better to fight for something than live for nothing.",
        "author": "General George S. Patton",
    },
    {
        "message": "Courage is fear holding on a minute longer.",
        "author": "General George S. Patton",
    },
    {
        "message": "We happy few, we band of brothers/For he today that sheds his blood with me/Shall be my brother.",
        "author": "William Shakespeare,\u2019\u2019 King Henry V\u2019\u2019",
    },
    {
        "message": "Cowards die many times before their deaths; The valiant never taste of death but once.",
        "author": "William Shakespeare, \u2018\u2019Julius Caesar\u2019\u2019",
    },
    {
        "message": "Never interrupt your enemy when he is making a mistake.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "There are only two forces in the world, the sword and the spirit. In the long run the sword will always be conquered by the spirit.",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "There will one day spring from the brain of science a machine or force so fearful in its potentialities, so absolutely terrifying, that even man, the fighter, who will dare torture and death in order to inflict torture and death, will be appalled, and so abandon war forever.",
        "author": "Thomas A. Edison",
    },
    {
        "message": "There are no atheists in foxholes, this isn't an argument against atheism, it's an argument against foxholes.",
        "author": "James Morrow",
    },
    {
        "message": "Live as brave men; and if fortune is adverse, front its blows with brave hearts.",
        "author": "Cicero",
    },
    {
        "message": "Courage and perseverance have a magical talisman, before which difficulties disappear and obstacles vanish into air.",
        "author": "John Quincy Adams",
    },
    {
        "message": "Courage is being scared to death - but saddling up anyway.",
        "author": "John Wayne",
    },
    {
        "message": "Above all things, never be afraid. The enemy who forces you to retreat is himself afraid of you at that very moment.",
        "author": "Andre Maurois",
    },
    {
        "message": "I have never made but one prayer to God, a very short one: 'O Lord, make my enemies ridiculous.' And God granted it.",
        "author": "Voltaire",
    },
    {
        "message": "Safeguarding the rights of others is the most noble and beautiful end of a human being.",
        "author": "Kahlil Gibran, \u2018\u2019The Voice of the Poet\u2019\u2019",
    },
    {"message": "He conquers who endures.", "author": "Persius"},
    {
        "message": "It is better to die on your feet than to live on your knees!",
        "author": "Emiliano Zapata",
    },
    {
        "message": "You know the real meaning of peace only if you have been through the war.",
        "author": "Kosovar",
    },
    {
        "message": "Those who have long enjoyed such privileges as we enjoy forget in time that men have died to win them.",
        "author": "Franklin D. Roosevelt",
    },
    {
        "message": "In war there is no substitute for victory.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "War is a series of catastrophes which result in victory.",
        "author": "Georges Clemenceau",
    },
    {"message": "In war, truth is the first casualty", "author": "Aeschylus"},
    {"message": "Incoming fire has the right of way.", "author": "Unknown"},
    {
        "message": "Mankind must put an end to war, or war will put an end to mankind.",
        "author": "John F. Kennedy",
    },
    {
        "message": "War does not determine who is right, only who is left.",
        "author": "Bertrand Russell",
    },
    {
        "message": "A ship without Marines is like a garment without buttons.",
        "author": "Admiral David D. Porter, USN",
    },
    {
        "message": "The press is our chief ideological weapon.",
        "author": "Nikita Khrushchev",
    },
    {
        "message": "Whether you like it or not, history is on our side. We will bury you!",
        "author": "Nikita Khrushchev",
    },
    {
        "message": "If the enemy is in range, so are you.",
        "author": "Infantry Journal",
    },
    {"message": "Cost of a single Javelin Missile: $80,000", "author": "Unknown"},
    {
        "message": "Cost of a single Tomahawk Cruise Missile: $900,000",
        "author": "Unknown",
    },
    {
        "message": "Cost of a single F-117A Nighthawk: $122 Million",
        "author": "Unknown",
    },
    {"message": "Cost of a single F-22 Raptor: $135 Million", "author": "Unknown"},
    {
        "message": "Cost of a single AC-130U Gunship: $190 Million",
        "author": "Unknown",
    },
    {"message": "Cost of a single B-2 Bomber: $2.2 Billion", "author": "Unknown"},
    {
        "message": "So long as there are men, there will be wars.",
        "author": "Albert Einstein",
    },
    {
        "message": "Aim towards the Enemy.",
        "author": "Instruction printed on US Rocket Launcher",
    },
    {
        "message": "I think the human race needs to think about killing. How much evil must we do to do good?",
        "author": "Robert McNamara",
    },
    {
        "message": "Any military commander who is honest will admit he makes mistakes in the application of military power.",
        "author": "Robert McNamara",
    },
    {
        "message": "You can make a throne of bayonets, but you cant sit on it for long.",
        "author": "Boris Yeltsin",
    },
    {
        "message": "The deadliest weapon in the world is a Marine and his rifle!",
        "author": "General John J. Pershing",
    },
    {
        "message": "Concentrated power has always been the enemy of liberty.",
        "author": "Ronald Reagan",
    },
    {
        "message": "Whoever stands by a just cause cannot possibly be called a terrorist.",
        "author": "Yassar Arafat",
    },
    {
        "message": "Nothing in life is so exhilarating as to be shot at without result.",
        "author": "Winston Churchill",
    },
    {
        "message": "War is delightful to those who have not yet experienced it.",
        "author": "Erasmus",
    },
    {"message": "Friendly fire, isn't.", "author": "Unknown"},
    {
        "message": "Diplomats are just as essential in starting a war as soldiers are for finishing it.",
        "author": "Will Rogers",
    },
    {
        "message": "I think that technologies are morally neutral until we apply them. It's only when we use them for good or for evil that they become good or evil.",
        "author": "William Gibson",
    },
    {
        "message": "All that is necessary for evil to succeed is for good men to do nothing.",
        "author": "Edmund Burke",
    },
    {
        "message": "The commander in the field is always right and the rear echelon is wrong, unless proved otherwise.",
        "author": "Colin Powell",
    },
    {
        "message": "Freedom is not free, but the U.S. Marine Corps will pay most of your share.",
        "author": "Ned Dolan",
    },
    {
        "message": "I know not with what weapons World War III will be fought, but World War IV will be fought with sticks and stones.",
        "author": "Albert Einstein",
    },
    {
        "message": "The truth of the matter is that you always know the right thing to do. The hard part is doing it.",
        "author": "Norman Schwarzkopf",
    },
    {
        "message": "If you know the enemy and know yourself you need not fear the results of a hundred battles.",
        "author": "Sun Tzu",
    },
    {
        "message": "Nearly all men can stand adversity, but if you want to test a man's character, give him power.",
        "author": "Abraham Lincoln",
    },
    {
        "message": "If we can't persuade nations with comparable values of the merits of our cause, we'd better reexamine our reasoning.",
        "author": "Robert McNamara",
    },
    {
        "message": "The tree of liberty must be refreshed from time to time with the blood of patriots and tyrants.",
        "author": "Thomas Jefferson",
    },
    {
        "message": "If the wings are traveling faster than the fuselage, it's probably a helicopter, and therefore, unsafe.",
        "author": "Unknown",
    },
    {
        "message": "Five second fuses only last three seconds.",
        "author": "Infantry Journal",
    },
    {
        "message": "If your attack is going too well, you're walking into an ambush.",
        "author": "Infantry Journal",
    },
    {
        "message": "No battle plan survives contact with the enemy.",
        "author": "Colin Powell",
    },
    {
        "message": "When the pin is pulled, Mr. Grenade is not our friend.",
        "author": "U.S. Army Training Notice",
    },
    {
        "message": "A man may die, nations may rise and fall, but an idea lives on.",
        "author": "John F. Kennedy",
    },
    {"message": "A leader leads by example, not by force.", "author": "Sun Tzu"},
    {
        "message": "If you can't remember, the claymore is pointed toward you.",
        "author": "Unknown",
    },
    {
        "message": "There are only two kinds of people that understand Marines: Marines and the enemy. Everyone else has a secondhand opinion.",
        "author": "General William Thornson",
    },
    {
        "message": "The more marines I have around, the better I like it.",
        "author": "General Clark, U.S. Army",
    },
    {
        "message": "Never forget that your weapon was made by the lowest bidder.",
        "author": "Unknown",
    },
    {
        "message": "Keep looking below surface appearances. Don't shrink from doing so just because you might not like what you find.",
        "author": "Colin Powell",
    },
    {
        "message": "Try to look unimportant; they may be low on ammo.",
        "author": "Infantry Journal",
    },
    {
        "message": "The world will not accept dictatorship or domination.",
        "author": "Mikhail Gorbachev",
    },
    {
        "message": "Tyrants have always some slight shade of virtue; they support the laws before destroying them.",
        "author": "Voltaire",
    },
    {
        "message": "Heroes may not be braver than anyone else. They're just brave five minutes longer.",
        "author": "Ronald Reagan",
    },
    {
        "message": "In the end, it was luck. We were *this* close to nuclear war, and luck prevented it.",
        "author": "Robert McNamara",
    },
    {
        "message": "Some people live an entire lifetime and wonder if they have ever made a difference in the world, but the Marines don't have that problem.",
        "author": "Ronald Reagan",
    },
    {
        "message": "It is generally inadvisable to eject directly over the area you just bombed.",
        "author": "U.S. Air Force Marshal",
    },
    {
        "message": "We sleep safely in our beds because rough men stand ready in the night to visit violence on those who would harm us.",
        "author": "George Orwell (Misattributed, was actually written by Richard Grenier[1])",
    },
    {
        "message": "If at first you don't succeed, call an air strike.",
        "author": "Unknown",
    },
    {"message": "Tracers work both ways.", "author": "U.S. Army Ordinance"},
    {
        "message": "Teamwork is essential, it gives them other people to shoot at.",
        "author": "Unknown",
    },
    {
        "message": "The real and lasting victories are those of peace, and not of war.",
        "author": "Ralph Waldo Emmerson",
    },
    {
        "message": "We're in a world in which the possibility of terrorism, married up with technology, could make us very, very sorry we didn't act.",
        "author": "Condoleeza Rice",
    },
    {"message": "All warfare is based on deception.", "author": "Sun Tzu"},
    {
        "message": "The indefinite combination of human infallibility and nuclear weapons will lead to the destruction of nations.",
        "author": "Robert McNamara",
    },
    {
        "message": "In war, you win or lose, live or die and the difference is just an eyelash.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "You can't say civilization don't advance, for in every war, they kill you in a new way.",
        "author": "Will Rogers",
    },
    {
        "message": "They'll be no learning period with nuclear weapons. Make one mistake and you're going to destroy nations.",
        "author": "Robert McNamara",
    },
    {
        "message": "It doesn't take a hero to order men into battle. It takes a hero to be one of those men who goes into battle.",
        "author": "General Norman Schwarzkopf",
    },
    {
        "message": "Any soldier worth his salt should be antiwar. And still, there are things worth fighting for.",
        "author": "General Norman Schwarzkopf",
    },
    {
        "message": "It is fatal to enter any war without the will to win it.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "Let your plans be as dark and impenetrable as night, and when you move, fall like a thunderbolt.",
        "author": "Sun Tzu",
    },
    {
        "message": "Anyone, who truly wants to go to war, has truly never been there before!",
        "author": "Larry Reeves",
    },
    {
        "message": "Whoever said the pen is mightier than the sword obviously never encountered automatic weapons.",
        "author": "General Douglas MacArthur",
    },
    {
        "message": "Whoever does not miss the Soviet Union has no heart. Whoever wants it back has no brain.",
        "author": "Vladimir Putin",
    },
    {
        "message": "My first wish is to see this plague of mankind, war, banished from the earth.",
        "author": "George Washington",
    },
    {
        "message": "Cluster bombing from B-52s are very, very, accurate. The bombs are guaranteed to always hit the ground.",
        "author": "USAF Ammo Troop",
    },
    {
        "message": "If a man has done his best, what else is there?",
        "author": "General George S. Patton",
    },
    {
        "message": "The bursting radius of a hand-grenade is always one foot greater than your jumping range.",
        "author": "Unknown",
    },
    {
        "message": "The tyrant always talks as if he's preserving the best interests of his people when he actually acts to undermine them.",
        "author": "Ramman Kenoun",
    },
    {
        "message": "Every tyrant who has lived has believed in freedom - for himself.",
        "author": "Elbert Hubbard",
    },
    {
        "message": "If our country is worth dying for in time of war let us resolve that it is truly worth living for in time of peace.",
        "author": "Hamilton Fish",
    },
    {
        "message": "Nationalism is an infantile disease. It is the measles of mankind.",
        "author": "Albert Einstein",
    },
    {
        "message": "We must not confuse dissent with disloyalty.",
        "author": "Edward R Murrow",
    },
    {
        "message": "I will fight for my country, but I will not lie for her.",
        "author": "Zora Neale Hurston",
    },
    {
        "message": "As we express our gratitude, we must never forget that the highest appreciation is not to utter words, but to live by them.",
        "author": "John F Kennedy",
    },
    {
        "message": "An eye for an eye makes the whole world blind.",
        "author": "Gandhi",
    },
    {
        "message": "Traditional nationalism cannot survive the fissioning of the atom. One world or none.",
        "author": "Stuart Chase",
    },
    {
        "message": "If you want a symbolic gesture, don't burn the flag; wash it.",
        "author": "Norman Thomas",
    },
    {
        "message": "The nation is divided, half patriots and half traitors, and no man can tell which from which.",
        "author": "Mark Twain",
    },
    {
        "message": "Patriotism is your conviction that this country is superior to all others because you were born in it.",
        "author": "George Bernard Shaw",
    },
    {
        "message": "If you are ashamed to stand by your colors, you had better seek another flag.",
        "author": "Anonymous",
    },
    {
        "message": "Revenge, at first though sweet, Bitter ere long back on itself recoils.",
        "author": "John Milton",
    },
    {
        "message": "A citizen of America will cross the ocean to fight for democracy, but won't cross the street to vote...",
        "author": "Bill Vaughan",
    },
    {
        "message": "Patriotism is supporting your country all the time, and your government when it deserves it.",
        "author": "Mark Twain",
    },
    {
        "message": "I love America more than any other country in this world; and, exactly for this reason, I insist on the right to criticize her perpetually.",
        "author": "James Baldwin",
    },
    {
        "message": "...dissent, rebellion, and all-around hell-raising remain the true duty of patriots.",
        "author": "Barbara Ehrenreich",
    },
    {
        "message": "Principle is OK up to a certain point, but principle doesn't do any good if you lose.",
        "author": "Dick Cheney",
    },
    {
        "message": "If an injury has to be done to a man it should be so severe that his vengeance need not be feared.",
        "author": "Machiavelli",
    },
    {
        "message": "Before you embark on a journey of revenge, you should first dig two graves.",
        "author": "Confucius",
    },
    {
        "message": "It is lamentable, that to be a good patriot one must become the enemy of the rest of mankind.",
        "author": "Voltaire",
    },
    {
        "message": "Ask not what your country can do for you, but what you can do for your country.",
        "author": "John F Kennedy",
    },
    {"message": "Revenge is profitable.", "author": "Edward Gibbon"},
    {"message": "Patriotism ruins history.", "author": "Goethe"},
    {
        "message": "I would not say that the future is necessarily less predictable than the past. I think the past was not predictable when it started.",
        "author": "Donald Rumsfeld",
    },
    {
        "message": "I only regret that I have but one life to give for my country.",
        "author": "Nathan Hale",
    },
    {"message": "Live well. It is the greatest revenge.", "author": "The Talmud"},
    {
        "message": "We know where they are. They're in the area around Tikrit and Baghdad and east, west, south and north somewhat.",
        "author": "Donald Rumsfeld",
    },
    {
        "message": "I was born an American; I will live an American; I shall die an American!",
        "author": "Daniel Webster",
    },
    {
        "message": "Patriotism varies, from a noble devotion to a moral lunacy.",
        "author": "WR Inge",
    },
    {
        "message": "It is easy to take liberty for granted when you have never had it taken from you.",
        "author": "Dick Cheney",
    },
    {
        "message": "A man's feet must be planted in his country, but his eyes should survey the world.",
        "author": "George Santayana",
    },
    {
        "message": "One good act of vengeance deserves another.",
        "author": "Jon Jefferson",
    },
    {
        "message": "You cannot get ahead while you are getting even.",
        "author": "Dick Armey",
    },
    {
        "message": "A nation reveals itself not only by the men it produces but also by the men it honors, the men it remembers.",
        "author": "John F. Kennedy",
    },
    {
        "message": "Patriotism is an arbitrary veneration of real estate above principles.",
        "author": "George Jean Nathan",
    },
    {
        "message": "Soldiers usually win the battles and generals get the credit for them",
        "author": "Napoleon Bonaparte",
    },
    {
        "message": "War is fear cloaked in courage.",
        "author": "General William C. Westmoreland",
    },
    {
        "message": "In peace, sons bury their fathers. In war, fathers bury their sons.",
        "author": "Herodotus",
    },
    {"message": "Don't get mad, get even.", "author": "John F. Kennedy"},
    {
        "message": "A man who would not risk his life for something does not deserve to live.",
        "author": "Martin Luther King",
    },
]


class DuckHunt(base.LoopCog):
    DUCK_PIC_URL = "https://cdn.icon-icons.com/icons2/1446/PNG/512/22276duck_98782.png"
    BEFRIEND_URL = "https://cdn.icon-icons.com/icons2/603/PNG/512/heart_love_valentines_relationship_dating_date_icon-icons.com_55985.png"
    KILL_URL = "https://cdn.icon-icons.com/icons2/1919/PNG/512/huntingtarget_122049.png"
    MW2_QUOTES = MW2_QUOTES
    ON_START = False
    CHANNELS_KEY = "hunt_channels"

    async def loop_preconfig(self):
        self.cooldowns = {}

    async def wait(self, config, _):
        await asyncio.sleep(
            random.randint(
                config.extensions.duck.min_wait.value * 3600,
                config.extensions.duck.max_wait.value * 3600,
            )
        )

    async def execute(self, config, guild, channel):
        if not channel:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "warning",
                "Channel not found for Duckhunt loop - continuing",
                send=True,
            )
            return

        self.cooldowns[guild.id] = {}

        start_time = datetime.datetime.now()
        embed = discord.Embed(
            title="*Quack Quack*",
            description="Befriend the duck with `bef` or shoot with `bang`",
        )
        embed.set_image(url=self.DUCK_PIC_URL)
        embed.color = discord.Color.green()

        message = await channel.send(embed=embed)

        response_message = None
        try:
            response_message = await self.bot.wait_for(
                "message",
                timeout=config.extensions.duck.timeout.value,
                # can't pull the config in a non-coroutine
                check=functools.partial(self.message_check, config, channel),
            )
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "error",
                "Exception thrown waiting for duckhunt input",
                exception=e,
            )

        await message.delete()

        if response_message:
            duration = (datetime.datetime.now() - start_time).seconds
            action = (
                "befriended" if response_message.content.lower() == "bef" else "killed"
            )
            await self.handle_winner(
                response_message.author, guild, action, duration, channel
            )
        else:
            await self.got_away(channel)

    async def got_away(self, channel):
        """Sends a "got away!" embed when timeout passes"""
        embed = discord.Embed(
            title="A duck got away!",
            description="Then he waddled away, waddle waddle, 'til the very next day",
        )
        embed.color = discord.Color.red()

        await channel.send(embed=embed)

    async def handle_winner(self, winner, guild, action, duration, channel):
        await self.bot.guild_log(
            guild,
            "logging_channel",
            "info",
            f"Duck {action} by {winner} in #{channel.name}",
            send=True,
        )

        duck_user = await self.get_duck_user(winner.id, guild.id)
        if not duck_user:
            duck_user = self.models.DuckUser(
                author_id=str(winner.id),
                guild_id=str(guild.id),
                befriend_count=0,
                kill_count=0,
            )
            await duck_user.create()

        if action == "befriended":
            await duck_user.update(befriend_count=duck_user.befriend_count + 1).apply()
        else:
            await duck_user.update(kill_count=duck_user.kill_count + 1).apply()

        await duck_user.update(updated=datetime.datetime.now()).apply()

        embed = discord.Embed(
            title=f"Duck {action}!",
            description=f"{winner.mention} {action} the duck in {duration} seconds!",
        )
        embed.color = (
            embed_colors.blurple() if action == "befriended" else embed_colors.red()
        )
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(
            url=self.BEFRIEND_URL if action == "befriended" else self.KILL_URL
        )

        await channel.send(embed=embed)

    def message_check(self, config, channel, message):
        # ignore other channels
        if message.channel.id != channel.id:
            return False

        if not message.content.lower() in ["bef", "bang"]:
            return False

        cooldowns = self.cooldowns.get(message.guild.id, {})

        if (
            datetime.datetime.now()
            - cooldowns.get(message.author.id, datetime.datetime.now())
        ).seconds < config.extensions.duck.cooldown.value:
            cooldowns[message.author.id] = datetime.datetime.now()
            self.bot.loop.create_task(
                message.author.send(
                    f"I said to wait {config.extensions.duck.cooldown.value} seconds! Resetting timer..."
                )
            )
            return False

        weights = (
            config.extensions.duck.success_rate.value,
            100 - config.extensions.duck.success_rate.value,
        )
        choice_ = random.choice(random.choices([True, False], weights=weights, k=1000))
        if not choice_:
            cooldowns[message.author.id] = datetime.datetime.now()
            self.bot.loop.create_task(
                message.channel.send(
                    content=message.author.mention,
                    embed=embeds.DenyEmbed(
                        message=f"Try again in {config.extensions.duck.cooldown.value} seconds"
                    ),
                )
            )

        return choice_

    def generate_failure_message(self, original_message):
        default_message = (
            "You failed to befriend the duck!"
            if original_message.content == "bef"
            else "You failed to kill the duck!"
        )

        if not self.MW2_QUOTES:
            return default_message

        failure_quote = random.choice(self.MW2_QUOTES)
        message = failure_quote["message"]
        author = failure_quote["author"]
        if not message or not author:
            return default_message

        return f'"{message}" -*{author}*'

    async def get_duck_user(self, user_id, guild_id):
        duck_user = (
            await self.models.DuckUser.query.where(
                self.models.DuckUser.author_id == str(user_id)
            )
            .where(self.models.DuckUser.guild_id == str(guild_id))
            .gino.first()
        )

        return duck_user

    @commands.group(
        brief="Executes a duck command",
        description="Executes a duck command",
    )
    async def duck(self, ctx):
        pass

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck stats",
        description="Gets duck friendships and kills for yourself or another user",
        usage="@user (defaults to yourself)",
    )
    async def stats(self, ctx, *, user: discord.Member = None):
        if not user:
            user = ctx.message.author

        if user.bot:
            await ctx.send_deny_embed(
                "If it looks like a duck, quacks like a duck, it's a duck!"
            )
            return

        duck_user = await self.get_duck_user(user.id, ctx.guild.id)
        if not duck_user:
            await ctx.send_deny_embed("That user has not partcipated in the duck hunt")
            return

        embed = discord.Embed(title="Duck Stats", description=user.mention)
        embed.color = embed_colors.green()
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck friendship scores",
        description="Gets duck friendship scores for all users",
    )
    async def friends(self, ctx):
        duck_users = (
            await self.models.DuckUser.query.order_by(
                -self.models.DuckUser.befriend_count
            )
            .where(self.models.DuckUser.befriend_count > 0)
            .where(self.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await ctx.send_deny_embed("It appears nobody has befriended any ducks")
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = (
                discord.Embed(title="Duck Friendships") if field_counter == 1 else embed
            )

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Friends: `{duck_user.befriend_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        ctx.task_paginate(pages=embeds)

    @util.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck kill scores",
        description="Gets duck kill scores for all users",
    )
    async def killers(self, ctx):
        duck_users = (
            await self.models.DuckUser.query.order_by(-self.models.DuckUser.kill_count)
            .where(self.models.DuckUser.kill_count > 0)
            .where(self.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await ctx.send_deny_embed("It appears nobody has killed any ducks")
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = discord.Embed(title="Duck Kills") if field_counter == 1 else embed

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Kills: `{duck_user.kill_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        ctx.task_paginate(pages=embeds)

    def get_user_text(self, duck_user):
        user = self.bot.get_user(int(duck_user.author_id))
        if user:
            user_text = f"{user.display_name}"
            user_text_extra = f"({user.name})" if user.name != user.display_name else ""
        else:
            user_text = "<Unknown>"
            user_text_extra = ""
        return f"{user_text}{user_text_extra}"
