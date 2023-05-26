# Application
Uses Google forum for Application
Uses Mongo for storing the application
Config setup
## Command Restrictions
.application get <application_id>
	User need manage application role
.application all <status (optional: approved/denied/pending)>
	User needs manage application role
.application approve <application_id>
	User need manage application role
.application deny <application_id> <reason>
	User need manage application role
.application remind 
	User need manage application role
## Normal use
User makes an application on Google forums
People with privileges can approve or deny the application 
## Expected errors
User name not found, ignore application
DM are close will not confirm application (Issue 213)
## Unexpected errors
User can submit muliple applications
User can ping by role 
One time application just failed outwrite

# Burn
No Dependencies
## Command Restrictions 
.burn
	No restrictions
## Normal use
.burn @Discord Member
	reply with a ping to the member/invoker with a random burn message
	And react to the message being burned with the 3 specific emojis
.burn username
	reply with a ping to the member/invoker with a random burn message
	And react to the message being burned with the 3 specific emojis
.burn id
	reply with a ping to the member/invoker with a random burn message
	And react to the message being burned with the 3 specific emojis
## Expected errors
Cannot burn a command
	Cound not find a message to reply to
Allows to burn same person multiple times, but does nothing

# ChaptGPT
No API

# Conch
No Dependencies
## Command Restrictions
.conch <question>
	None
.8ball <question>
	None
.8b <question>
	None
## Normal use
.conch Question
	Repeats question with a ? (crops to 256 without a ?)
	Replies from a list of responses
.8ball Question
	Repeats question with a ? (crops to 256 without a ?)
	Replies from a list of responses
.8b Question
	Repeats question with a ? (crops to 256 without a ?)
	Replies from a list of responses
## Expected errors
.conch
	Return a deny embed with "You need to add a question"
## Unexpected errors
.conch @role
	Check to see if the bot can ping role

# Correct
No Dependencies
## Command Restrictions
.correct [to_replace] [replacement]
	None
.c [to_replace] [replacement]
	None
## Normal use
.correct [to_replace] [replacement]
	Replies with a CorrectEmbed with the new
.c [to_replace] [replacement]
	Replies with a CorrectEmbed with the new
## Expected errors
.correct or .c
	Replies with a Deny Embed "You did not provide the command argument: `to_replace: str`"
.correct or .c [to_replace] 
	Replies with a Deny Embed "You did not provide the command argument: `replacement: str`"
.correct or .c "incorrect string" "correction string"
	Replies with a Deny Embed "I couldn't find any message to correct"
## Unexpected errors
.correct or .c
	Cannot correct a message that start with the prefix of the bot

# Directory
Disabled

# Duck
User Postgres Database
Config setup
## Command Restrictions
.duck stats
	None
.duck friends
	None
.duck killers
	None
## Normal use
Spawns ducks every so often based on channel in config file
User can use Bang or Bef to kill or friend duck in 60 seconds
Random times it will make user wait for a cooldown (5 seconds) to kill or friend duck
	Should display quotes (issue #73)
If no one kills or friends duck in 60 seconds
	Send an embed saying the Duck got away
.duck stats
	Defaults to author for their duck stats
.duck stats Member
	Displays duck stats for that member
.duck friends
	Displays leaderboard of duck friends
.duck killers
	Displays leaderboard of duck killers
## Expected errors
.duck stats Member with no stats
	Sends Deny Embed with "That user has no partcipated in the duck hunt"
.duck stats non Member
	Sends deny Embed with "I couldn't find the server member: "non Member"

# Dumpdbg
Uses server API
Uses Praiser
Config setup
## Command Restrictions
.dumpdbg [.dmp file]
	Has cooldown 1 time every 60 seconds
## Normal use
.dumpdbg [.dmp file]
	Sends off to server for praising and returns a txt file
	Give an embed for Dumps successfuly returned with a link to the pasted txt file
Aliases are:
	dump, debug-dump, debug_dump, debugdump
## Expected errors
.dump with a zip
	Return Deny Embed with "No valid dumps detected!"
## Unexpected errors
.dump with a file renamed to dmp
	return a Deny embed "I ran into error processing your command: Command raised an exception: KeyError: 'url'"

# Embed
No Dependencies
## Command Restrictions
.embed |embed-list-json-upload|
	None
.embed keep |embed-list-json-upload|
## Normal use
.embed <attach json>
	Displays how the json works
## Expected errors
.embed
	send Deny embed "Please provide a jSON file for your embeds"
.embed keep |embed-list-json-upload|
	Will send a direct message "I couldn't generate all of your embeds" if one or more embed failed, but not delete them
.embed |embed-list-json-upload|
	Will send a direct message "I couldn't generate all of your embeds, so I gave you a blank slate" if the json is broken, but not too broken
.embed |embed-list-json-upload|
	Will send a deny embed if the json has errors in it
## Unexpected errors
.embed |embed-list-json-upload|
	Send a Deny embed that command raised an exception: AttributeError: 'Context' object has no attribue 'get_json_from_attachments' (issue #183)

# Emoji
Uses emoji python library
## Command Restrictions
.emoji reaction [message] @Member
	Has premissions to add_reactions
## Normal use
.emoji message "abc"
	Sends confirm embed with the message in emojis
.emoji msg "abc"
	Message for the help command to display options
	Sends confirm embed with the message in emojis
.emoji reaction "message to react with" @Member
	Will react to the last message by user with message in emoji
## Expected errors
.emoji reaction "message" @Member
	Has a dupiclate emoji sends deny embed "Invalid message! Make sure there are no repeat characters!"
.emoji reaction "message" @non Member
	Replies with a deny embed "I couldn't find the server member: "Non member""
.emoji message "message" 
	Send deny embed if cannot find an emoji for something in "message" with "I can't get any emoji letters from your message!"
## Unexpected errors
.emoji reaction "string longer than 20 characters" @Member
	Will send emojis up to 20 times before errors out with a deny embed stating Forbidden: 403 Maximum number of reactions
Some weird actions when using codeblocks	
	
# Factoids
Uses Postgres for database
Config setup
## Command Restrictions
.factoid remember [factoid-name] [factoid-output] |optional-embed-json-upload|
	User needs manage factoids role
.factoid forget [factoid-name]
	User needs manage factoids role
.factoid json [factoid-name]
	User needs manage factoids role
.factoid loop [factoid-name] [cron_config] [channel]
	User needs manage factoids role
.factoid deloop [factoid-name] [channel]
	User needs manage factoids role
.factoid job [factoid-name] [channel]
	User needs manage factoids role
.factoid jobs
	None
.factoid all
	None
.factoid hide [Factoid-name]
	User need permissions to kick_members
.factoid unhide [Factoid-name]
	User need permissions to kick_members
## Normal use
.factoid loop <factoid-name> < cron_config> <channel>
	Will loop the factoid as often as you want in the channel you would like
.factoid forget <factoid-name>
	Will forget the factoid that is saved with that name
.factoid remember <factoid-name> <factoid-output> <optional | embed json>
	Will remember a factoid to call later
.factoid job <factoid-name> <channel>
	Will display the loop config for the <factoid-name> and channel along with the factoid
.factoid deloop <factoid-name> <channel>
	Will deloop the <factoid-name> on the channel
.factoid unhide <factoid-name>
	Will hide the factoid-name from the list of all the factoids
.factoid all or .factoid lsf
	Will provide a list of all unhidden factoid in a confirm embed through the paste
.factoid hide <factoid-name>
	Will hide the factoid-name from the list of all
.factoid jobs
	Will provide an embed displaying which factoids are in jobs currently
.factoid json <factoid-name>
	Will provide a json for the factoid name
## Expected errors
.factoid json <factoid-name>
	If factoid-name has no json will send deny embed "There is no embed config for that factoid"
.factoid
	Will send help embed with a list of all options for factoid command
.factoid loop <factoid-name> < cron_config> <channel>
	Will check if factoid-name exist otherwise send deny embed "That factoid does not exist"
	Will check if factoid-name is already looping in a channel send deny embed "That factoid is already looping in this channel"
.factoid remember <factoid-name>
	Will send a deny embed "You did not provide the command argument: `message: str`"
	Will send a deny embed "I am unable to do that because you lack the role(s): [<Role id=773304890772029470 name='Trusted'>, <Role id=749314516801552416 name='Moderator'>]" if user does not have premissions
.factoid job <factoid-name> <channel>
	Send deny embed for "That job does not exist" if job does not exist in that channel or factoid name is wrong
	Send deny embed "I couldn't find the channel: "<channel>" if channel is wrong
.factoid job
	Send deny embed "You did not provide the command argument: `factoid_name: str`"
.factoid job <factoid-name>
	Send deny embed "You did not provide the command argument: `channel: discord.channel.TextChannel`"
.factoid deloop
	Send deny embed "You did not provide the command argument: `factoid_name: str`"
.factoid deloop <factoid-name>
	Send deny embed "You did not provide the command argument: `channel: discord.channel.TextChannel`"
.factoid deloop <factoid-name> <channel>
	Send deny embed for "That job does not exist" if job does not exist in that channel or factoid name is wrong
	Send deny embed "I couldn't find the channel: "<channel>" if channel is wrong
.factoid unhide <factoid-name>
	send deny embed "I couldn't find that factoid" if name doesn't exist
	send deny embed "That factoid is already unhidden" if factoid is unhidden.
.factoid hide <factoid-name>
	send deny embed "I couldn't find that factoid" if name doesn't exist
	send deny embed "That factoid is already hidden" if factoid-name is hidden
.factoid jobs
	Send deny embed "There are no registered factoid loop jobs for this guild" if no jobs exists
.factoid json <factoid-name>
	Send deny embed "I couldn't find that factoid" if name doesn't exist
## Unexpected errors
.factoid forget <factoid-name>
	Will Send a confirm embed that the factoid was deleted
	Will send a deny embed that the factoid doesn't exists.
Don't know what will happen to jobs if a channel is deleted

# Gate
Config setup
## Command Restrictions
.gate intro
	User needs permissions to manage_messages
	guild_only
## Normal use
Set Gate channel in config
User sends approved message and will be assigned a role
Approved message will be deleted after wait time (default = 60 seconds)
All messages beside admin of bot will be deleted in channel.
.gate intro
	Send the message in the config file to the gate channel.
## Expected errors
.gate intro
	Sends deny embed "That command is only usable in the gate channel" if not in gate channel.
.gate
	Send help embed that list how to use the command.

# Giphy
Uses Giphy API
## Command Restrictions
.giphy [query]
	None
## Normal use
.giphy test
	Will return a gif of test with emoji reactions to search between them.
## Expected errors
.giphy alajfkidoiawhngonaodwsfjoniafds
	Will return a deny embed "No search results found for: alajfkidoiawhngonaodwsfjoniafds"
.giphy
	Will return deny embed "You did not provide the command argument: `query: str`"

# Google
Uses Google CSE API
Uses Youtube API
## Command Restrictions
.googe search [query]
	Has cooldown of 3 times in 60 seconds
.googe images [query]
	Has cooldown of 3 times in 60 seconds
## Normal use
.google search [query]
.g search [query]
.g s [query]
.google s [query]
	Will return embed with link of first google search result for <message>
.google images [query]
.google i [query]
.google is [query]
.g images [query]
.g i [query]
.g is [query]
	Will return embed with first image in google image search result
.youtube [query]
.yt [query]
	Will return first link of a youtube search
## Expected errors
.google search
	Will return deny embed "You did not provide the command argument: `query: str`"
.youtube
	Will return deny embed "You did not provide the command argument: `query: str`"

# Grab
Uses Postgres
Config setup
## Command Restrictions
.grab [message_id]
	Checks for invalid_channel
.grabs all [@Member]
	Checks for invalid_channel
.grabs random [@Member]
	Checks for invalid_channel
## Normal use
.grab [message_id]
	Will grab the message from the message_id and save it under the user who grabbed it
.grabs all [@Member]
	Send embed with all grabs for Member
.grabs random [@Member]
	Will get a random grab from the Member
## Expected errors
.grab
	Send deny embed "You did not provide the command argument: message: `discord.message.Message`"
.grabs all
.grabs random
	Send deny embed "You did not provide the command argument: user_to_grab: `discord.member.Member`"
.grab <message_id>
	Send deny embed "I couldn't find the message: "<message_id>"" if not correct message_id

# Hangman
Config setup
## Command Restrictions
.hangman start [word]
	None
.hangman guess [letter]
	None
.hangman redraw
	None
.hangman stop
	Check if user can stop game
## Normal use
.hangman start [word]
	Will start a hangman game with the word and draw the picture with dashes for the length of word.
.hangman redraw
	Will redraw the current state of hangman
.hangman stop
	Will stop the current game of the hangman
.hangman guess [letter]
	Will guess the letter in the game and send an embed with result
## Expected errors
.hangman start [word]
	Will send deny embed "There is a game in progress for this channel" if another game isn't finished
	Will send deny embed "I ran into an error processing your command: Command raised an exception: HTTPException: 400 Bad Request (error code: 50035): Invalid Form Body In embeds.0.title: Must be 256 or fewer in length." If length is longer that 128 because it adds spaces
.hangman redraw
	Will send deny embed "There is a game in progress for this channel" if game isn't started
.hangman guess [letter]
	Will send deny embed "You can only guess a letter" if you try to guess a non letter
## Unexpected errors
Game does not stop when word is guess, or number of guesses is up.

# Hello
Uses python emoji library
## Command Restrictions
.hello
	None
## Normal use
.hello
	Bot will react with "HEY" in emojis to command call

# HTD
No Dependencies
## Command Restrictions
.htd [value]
	None
## Normal use
.htd 0x<hex>
	Will return an embed with the Decimal, Binary, and Ascii equivalent if there is one
.htd 0b<binary>
	Will return an embed with the Decimal, Hex, and Ascii equivalent if there is one
.htd <Decimal>
	Will return an embed with the Hex, Binary, and Ascii equivalent if there is one
.htd <hex> + <hex>
.htd <hex> + <Binary>
.htd <hex> + <Decimal>
	Will return the addition of the two values
.htd <hex> - <hex>
.htd <hex> - <Binary>
.htd <hex> - <Decimal>
	Will return the subtraction of the two values
.htd <hex> * <hex>
.htd <hex> * <Binary>
.htd <hex> * <Decimal>
	Will return the multiplication of the two values
.htd <hex> / <hex>
.htd <hex> / <Binary>
.htd <hex> / <Decimal>
	Will return the division of the two values
## Expected errors
.htd <hex> +
	Will return deny embed "I ran into an error processing your command: Command raised an exception: IndexError: string index out of range"
.htd + <hex>
	Will return deny embed "Unable to perform calculation, are you sure that equation is valid?"
.htd <Decimal> / 0
	Will return deny embed "I ran into an error processing your command: Command raised an exception: ZeroDivisionError: division by zero"
## Unexpected errors
ascii ending just new line after new line after new line, and it will just extend the embed into infinity
Could also spell out bad words
	
# Hug
No Dependencies
## Command Restrictions
.hug [@Member]
	None
## Normal use
.hug @Member
	Will return an embed from a list of ways to hug
## Expected errors
.hug
	Return deny embed "You did not provide the command argument: user_to_hug: `discord.member.Member`" for Member not found
.hug yourself
	Return deny embed "Let's be serious"

# Ipinfo
Uses API ipinfo.io
## Command Restrictions
.ipinfo [ip]
	Has cooldown of 1 time every 30 seconds
## Normal use
.ipinfo <ip address>
	Will return the embed with information from geodata on the ip address.
## Expected errors
.ipinfo
	Return deny embed "You did not provide the command argument: `ip_address: str`" if no string provided
.ipinfo [ip]
	Will return deny embed "I couldn't find that IP" if ip address is wrong
## Unexpected errors
.ip [ip] 
	The alias does not return anything

# Iss
Uses API open-notify.org
Uses Geocode.xyz
## Command Restrictions
.iss
	Has cooldown of 1 time every 60 seconds
## Normal use
.iss
	Return embed to track the International Space Station with location latitude and Longitude

# Joke
Uses API from jokeapi.dev
## Command Restrictions
.joke
	Has cooldown of 1 time every 60 seconds
## Normal use
.joke
	returns an embed with a random joke from jokeapi.dev

# Kanye
API key from api.kanye.restrictions
## Command Restrictions
.kanye
	Has cooldown of 1 time every 60 seconds
## Normal use
.kanye
	Will return an embed with a random quote from the API

# Lenny
No Dependencies
## Command Restrictions
.len
	None
## Normal use
.len
	Returns a rand face from a list

# Logger
No Dependencies
## Normal use
Should log every message in the logger channel
Should log the url for an attachment in the logger channel

# Mock
No Dependencies
## Command Restrictions
.mock [@user]
	None
.sb [@user]
	None
## Normal use
.mock @Member
.sb @Member
	returns embed of last message with alternating cases for the message
## Expected errors
.mock
.sb
	Return deny embed "You did not provide the command argument: user_to_mock: `discord.member.Member`" if member doesn't exist
.mock @Member
.sb @Member
	If member does not exist will return "I coudn't find the server member: "<Member>""

# News
Uses API for newsapi.org
## Command Dependencies
.news random [category] (optional)
	Has cooldown of 1 time every 30 seconds
## Normal use
.news random [category] (optional)
	Will return a random news story from all or the specific category you pick out.
## Expected errors
.news
	Will return the help embed for command usage
.news [category]
	Will return embed asking to display help command

# Poll
Uses API strawpoll.com
## Command Restrictions
.poll example
	None
.poll creates |json-upload|
	None
.poll generate |json-upload|
	None
.strawpoll generate |json-upload|
	None
.strawpoll example
	None
## Normal use
.poll example 
	returns a json file of an exmaple poll
.poll create |json-upload|
	Takes the json and creates an embed with a poll, adds reactions for the options
.poll generate |json-upload|
	Takes the json and creates an embed with a poll, adds reactions for the options
.strawpoll generate |json-upload|
	uses the json to upload a poll to strawpoll.com
.strawpoll example
	returns a json with an example of the poll for strawpoll
## Expected errors
Timeouts has to be between 10 and 300
Will error on an invalid json
.poll generate <json>
	Will send a deny embed "I need between 2 and 5 options! (options key)" if only one option is given
	Will send a deny embed "I need the poll question to be a string (question key)" if question isn't a string
	Will send a deny embed "Nobody voted in the poll, so I won't bother showing any results" if no unique results were found.
	Will send a deny embed "I did not find a poll question (question key)" if no question in json
	Will send a deny embed "I need the poll options to be a list (question key)" if the options are not a list
.poll generate
	Send deny embed "I couldn't find any data in your upload" with no json

# Protect
Uses Postgres
## Command Restrictions 
.ban
	The Bot and a user needs premissions to ban_members
.unban
	The Bot and a user needs premissions to ban_members
.kick
	The bot and a user needs premissions to kick_members
.warn
	The bot and a user needs premissions to kick_members
.unwarn
	The bot and a user needs premissions to kick_members
.warnings
	The bot and a user needs premissions to kick_members
.mute
	The bot and a user needs premissions to kick_members
.unmute
	The bot and a user needs premissions to kick_members
.purge
	The bot and a user needs premissions to manage_messages
## Normal use
Will not allow users to mass mention, Will warn user who tries to do it.
Will paste a message over 750 characters into a paste.
.ban @User |optional -reason|
	Will ban the user from the server including users not in server. return user modified embed to show users has been banned.
.unban @User |optional -reason|
	Will unban the user from the server including users not in server. return user modified embed to show users has been unbanned.
.kick @Member |optional -reason|
	Will kick a member from the server. return user modified embed to show user has been kicked
.warn @Member |optional -reason|
	Will set a warn on a member with a reason, once you get 3 warnings it will ban the member
.unwarn @Member |optional -reason|
	Will remove the warnings from a Member
.warnings @User
	Will display all the warnings for a Member
.mute @Member |optional -reason|
	Will add a "Muted" role to the Member 
.unmute @Member |optional -reason|
	Will remove the "Muted role from the Member
.purge x <Number>
	Will purge the last <Number> of messages including the bot command
.purge d <Number>
	Will purge the last number of messages since <Number> minutes ago
## Expected errors
.ban @User
	Will send a deny embed "You cannot do that to yourself" if you try to ban yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to ban the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to ban someone who's role is over than you.
	Will send a deny embed "User is already banned" if user is already banned
	Will send a deny embed "I couldn't find the user <@User>" if not a user of discord
	Will send a deny embed "I ran into an error processing your command: Command raised an exception: Forbidden: 403 Forbidden (error code: 50013): Missing Permissions" if the bot does not have a top role high enough to ban
.unban @User
	Will send a deny embed "You cannot do that to yourself" if you try to unban yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to unban the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to unban someone who's role is over than you.
	Will send a deny embed "User is not banned, or does not exist" if user is already unbanned
	Will send a deny embed "I couldn't find the user <@User>" if not a user of discord
.kick @Member
	Will send a deny embed "You cannot do that to yourself" if you try to kick yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to kick the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to kick someone who's role is over than you.
	Will send a deny embed "I couldn't find the server member: <@Member> if member is not in server or they exist
.warn @Member
	Will send a deny embed "You cannot do that to yourself" if you try to warn yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to warn the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to warn someone who's role is over than you.
	Will send a deny embed "I couldn't find the server member: <@Member>" if not a user of discord or not in server
	Will send a deny embed "I ran into an error processing your command: Command raised an exception: Forbidden: 403 Forbidden (error code: 50013): Missing Permissions" after three warnings if the bot cannot ban a Member, also clears the warning that is issued.
.unwarn @Member
	Will send a deny embed "You cannot do that to yourself" if you try to unwarn yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to unwarn the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to unwarm someone who's role is over than you.
	Will send a deny embed "There are no warnings for that user" if the member has no warnings
.warnings @User
	Will send a deny embed "There are no warnings for that user" if User has no warnings or user does not esists
.mute @Member
	Will send a deny embed "You cannot do that to yourself" if you try to mute yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to mute the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to mute someone who's role is over than you.
	Will send a deny embed "I couldn't find the server member: @Member" if the Member is not in server or if Member does not exists
	Will send a deny embed "The `Muted` role does not exist" if the "Muted" role does not exists
.unmute @Member
	Will send a deny embed "You cannot do that to yourself" if you try to unmute yourself
	Will send a deny embed "It would be silly to do that to myself" if you try to unmute the bot
	Will send a deny embed "Your top role is not high enough to do that to `{target}`" if you try to unmute someone who's role is over than you.
	Will send a deny embed "I couldn't find the server member: @Member" if the Member is not in server or if Member does not exists
	Will send a deny embed "The `Muted` role does not exist" if the "Muted" role does not exists
.purge x <non int>
	Will send a deny embed "I ran into an error processing your command: Converting to "int" failed for parameter "amount"." if a non interger is provided
.purge d <non int>
	Will send a deny embed "I ran into an error processing your command: Converting to "int" failed for parameter "duration_minutes"." if a non interger is provided
## Extra Notes
Can add a string map with words or phrases to make a response to. Will also take in regex. 
If added in a codeblock will ping in the stack trace because it paste as plane text.

# Relay

# Roll
Discord Library Random
## Command Restrictions
.roll
	None
## Normal use
.roll
	Will default and pick a random number form 1-100
.roll <int>
	Will set a new minimum and choose a number between <int> and 100
.roll <int> <int>
	Will Choose a value between <int> and <int>
## Expected errors
.roll <int > 100>
	Will send a deny embed "I ran into an error processing your command: Command raised an exception: ValueError: empty range for randrange() (101, 101, 0)" indicating the value is out of range
.roll <decimal>
	Will send a deny embed "I ran into an error processing your command: Converting to "int" failed for parameter "min"." if you put in a non interger value
.roll <int> <non int>
	Will send a deny embed "I ran into an error processing your command: Converting to "int" failed for parameter "max"." if cannot find an int for second parameter

# Rules
Uses Mongo
## Command Restrictions
.rule
	None
.rule edit |json|
	Author needs administrator
.rule get <int>
	None
.rule all
	None
## Normal use
.rule edit
	Will return a json file with sample rules.
.rule edit <json>
	Will update the rules based on the json provided
.rule get <int>
	Will return rule <int> in an embed with description
.rule get <int>,<int>
	Will return all rules provided in different embed with description
.rule get <int>,<int> (same interger)
	Will return all rules provided in a different embed with description (but will not paste same rule twice)
.rule all
	Will return all rules in a single embed with description of each.
## Expected errors
.rule
	Will return a help embed of the options to use with the rule command
.rule edit |json|
	Will send a success message even if it is an invalid json for the rules
.rule get <non int>
	Will send a deny embed "Please specify a rule number"
.rule get <int> (out of range)
	Will send a deny embed "Rule number <int> doesn't exist"
.rule get <int>,<non int>,<int>
	Will send a deny embed "Please specify a rule number"
.rule get <int>,<int>,<int> (one a non rule)
	Will print all the rules that exists then send a deny embed with which one did not. (will not repeat duplicates of rules if expanded, but will repeate of rules that do not exist)
.rule get <int <=0>
	Will send deny embed "That rule number is invalid"

# Spotify
Uses Spotify API
## Command Restrictions
.spotify
	Has cooldown for 3 times in 60 seconds
## Normal use
.spotify <track name>
	Will return a result from Spotify with the <track name> with up to 3 results form the US market 
## Expected errors
.spotify
	Will return a deny embed with "You did not provide the command argument: query: str"
.spotify <track name>
	Will return a deny embed with "I couldn't find any results"
.spotify <track name>
	Will return a deny embed with "I couldn't authenticate with Spotify" if no API or cannot be reached
	
# Translate
Uses mymemory.translated.net API
## Command Restrictions
.translate <message (in quotes)> <sorce language code> <Destination language code>
	has cooldown for 1 time in 60 seconds
## Normal use
.transale <message (in quotes)> <sorce language code> <Destination language code>
	Will send a confirm embed with the translated message
## Expected errors
.translate
	Will send deny embed with "You did not provide the command argument: message"
.translate <message>
	Will send deny embed with "You did not provide the command argument: src: str"
.translate <message> <src language code>
	Will send a deny embed with "You did not provide the command argument: dest: str"
.translate <message> <scr language code> <dest language code>
	Will send a deny embed "I wasn't able to understand your command because of an unexpected quote (")" if you try to add quotes in the string

# Urban
Uses urbandictionary.com API for base term
Uses urbandictionary.com API for see more terms
## Command Restrictions
.urb <query>
	Has cooldown of 3 times in 60 seconds
## Normal use
.urb test
.urban test
.urbandictionary test
	Will return a result embed with a link to the urbandictionary page and a short summy of the define (up to 10 results)
## Expected errors
.urb
    Will return a deny embed "You did not provide the command argument: `query: str`"
.urb ugekuahskdddfgehasjdf
    Will return an deny embed "No results found for: <query>"

# Warcraft
Not in Use

# Weather
Uses API from openweathermap.org
## Command Restrictions
.weather [city/town] [state-code] [country-code]
	Has cooldown of 3 times in 60 seconds
## Normal use
.weather [city/town] [state-code] [country-code]
.wea [city/town] [state-code] [country-code]
.we [city/town] [state-code] [country-code]
	Will return an embed with the weather from the place you selected
## Expected errors
.weather <invalid configuration>
	Will send a deny embed "I could not find the weather from your search"

# Who
Postgres
## Command Restrictions
.whois [@Member]
	None
.note set [@Member] [note]
	User needs permissions to kick_members
.note clear [@Member]
	User needs permissions to kick_members
.note all [@Member]
	User needs permissions to kick_members
## Normal use
.whois [@Member]
	Will return an embed with information on the Member with notes
.note set [@Member] [note]
	Will set a note on the Member and provide a confirm embed "Note created for @Member"
.note clear [@Member]
	Will ask you if you want to erase notes for user, checkmark to confirm and erase note
.note all [@Member]
	Will return a json with all the notes on the user
## Expected errors
.whois [@Member]
	Will return a deny embed "I couldn't find server member: @Member" if member does no exist or is part of guild
.note
	Will return help embed with options for commands of Who
.note set [@Member]
	Will return a deny embed "You did not provide the command argument: `body: str`" if no note
.note clear [@Member]
	Will return a deny embed "I couldn't find server member: @Member" if member does no exist or is part of guild
.note all [@Member]
	Will return a deny embed "I couldn't find server member: @Member" if member does no exist or is part of guild

# Wolfram
Uses API from wolframalpha.com
## Command Restrictions
.wa [query]
.math [query]
.wolframalpha [query]
.jarvis [query]
	Has cooldown of 3 times every 60 seconds
## Normal use
.wa [query]
.math [query]
.wolframalpha [query]
.jarvis [query]
	Will return an embed with the simple answer to the [query]
## Expected errors
.wa [query]
.math [query]
.wolframalpha [query]
.jarvis [query]
	Will return a deny embed "Wolfram|Alpha ran into an error" if no API or API error
	Will return a deny embed "Wolfram|Alpha did not like that question" if no results are found

# Wyr
No Dependencies
## Command Restrictions
.wyr
	None
## Normal use
.wyr
	Return an embed with the generated question

# xkcd
Uses APIs from xkcd.com
## Command Restrictions
.xkcd random
.xkcd number [number]
.xkcd # [number]
	Has cooldown of 3 times every 60 seconds
## Normal use
.xkcd random
	Will return an embed with a random comic from xkcd
.xkcd number [number]
	Will return a specific number comic from xkcd
.xkcd # [number]
	Will return a specific number comic from xkcd
## Expected errors
.xkcd
	Will return the help embed to display how to use commands in xkcd
.xkcd number [number]
	Will return a deny embed "I had trouble looking up XKCD's comics" if API goes above 200 seconds
.xkcd number 1023103132
	Will return a deny embed "I ran into an error processing your command: Command raised an exception: ContentTypeError: 0, message='Attempt to decode JSON with unexpected mimetype: text/html; charset=utf-8', url=URL('https://xkcd.com/1023103132/info.0.json')" if cannot find the right number
	
# Bot Commands

## Normal use
.extension unload [extension-name]
	Returns a confrim embed "I've unloaded that extension"
## Expected errors
.extension unload [extension-name]
	Returns a confrim embed "I've unloaded that extension" Even if name is not an extension
	Returns a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command."
.extension unload
	Return a deny embed "You did not provide the command argument: `extension_name: str`"

## Normal use
.extension register [extension-name] |python-file-upload|

## Expected errors
.extension register [extension-name]
	Return a deny embed "You did not provice a Python file upload"
.extension register [extension-name] |python-file-upload|
	Return a deny embed "I don't recognize your upload as a Python file" if you try to upload a differnt file type
	return a deny embed "I ran into an error processing your command: Command raised an exception: TypeError: argument of type 'coroutine' is not iterable" If python file has an error
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.extension register
	Return a deny embed "You did not provide the command argument: `extension_name: str`"

## Normal use
.extensions satus [extension-name]
	Return an embed that tells status of [extension-name] loaded/unloaded
## Expected errors
.extensions satus [extension-name]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Will return an embed saying extension is unloaded even if wrong name
.extension status
	Return a deny embed "You did not provide the command argument: `extension_name: str`"

## Normal use
.extension load [extension-name]
	Return a confirm embed "I've loaded that extension"
## Expected errors
.extension load [extension-name]
	Will return a confirm embed "I've loaded that extension" even if name is wrong or extension is already loaded.
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.extension load
	Return a deny embed "You did not provide the command argument: `extension_name: str`"

## Normal use
.command enable [command-name]
	Return a confirm embed "Successfully enabled command: [command-name]"
## Expected errors
.command enable [command-name]
	Return a deny embed "Command [command-name] is already enabled!" If it is already enabled
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "No such command: [command-name]" if command doesn't exists
.command enable
	Return a deny embed "You did not provide the command argument: `command_name: str`"

## Normal use
.command disable [command-name]
	Return a confrim embed "Successfully disabled command: [command-name]"
## Expected errors
.command disable [command-name]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "No such command: [command-name]" if command doesn't exists
	Return a deny embed "Command [command-name] is already disabled!" If it is already disabled
.command disable
	Return a deny embed "You did not provide the command argument: `command_name: str`"
## Note
Disabling `command` means you cannot enable any commands you disabled per session 

## Normal use
.set game [game-name]
	return a confrim embed "Successfully set game to [game-name]"
## Expected errors
.set game [game-name]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.set game
	Return a deny embed "You did not provide the command argument: `game_name: str`"
## Note
[game-name] is limited to 128 characters will set to none if over that by default.

## Normal use
.set nick [nickname]
	Return a confrim embed "Seuccessfully set nick to: [nickname]"
## Expected errors
.set nick
	Return a deny embed "You did not provide the command argument: `nick: str`"
.set nick [nickname]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	
## Normal use
.echo channel [channel-id] [message]
	Return a conrim embed "Message sent" Returns a message in the channel from the bot
## Expected errors
.echo channel [channel-id] [message]
	Return a deny embed "I couldn't find that channel" if the bot could not find channel id.
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.echo channel [channel-id]
	Return a deny embed "You did not provide the command argument: `message: str`"
.echo channel
	return a deny embed "You did not provide the command argument: `channel_id: int`"

## Normal use
.echo user [user-id] [message]
	Return a conrim embed "Message sent" DM user your message
## Expected errors
.echo user [user-id] [message]
	Return a deny embed "I ran into an error processing your command: Command raised an exception: Forbidden: 403 Forbidden (error code: 50007): Cannot send messages to this user" if cannot dm user 
	I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command.
	Return a deny embed "I ran into an error processing your command: Command raised an exception: NotFound: 404 Not Found (error code: 10013): Unknown User" If cannot find user
.echo user [user-id]
	Return a deny embed "You did not provide the command argument: `message: str`"
.echo user 
	Return a deny embed "You did not provide the command argument: `user_id: int`"

## Normal use
.restart
	Return a confirm embed "Rebooting! Beep boop!" and restart the bot
.reboot
	Return a confirm embed "Rebooting! Beep boop!" and restart the bot
## Expected errors
.restart
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin

## Normal use
.leave [guild-id]
	The bot will leave the server it is in
## Expected errors
.leave [guild-id]
	Return a deny embed "I don't appear to be in that guild" if bot is not in that server
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin

## Normal use
.bot
	Return an embed with time started, latency, description, and server
## Expected errors
.bot
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin

## Normal use
.issue [title] [description]
	Return an embed saying the issue was created with issue number and url
## Expected errors
.issue [title] [description]
	Return a deny embed "I was unable to create your issue (status code 401)" if could not create issue
	Return a deny embed "I don't have a Github API key" if not API key
	Return a deny embed "I don't have a Github repo configured" if name of repo does not match an existing one
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.issue [title]
	Return a deny embed "You did not provide the command argument: `description: str`"
.issue
	Return a deny embed "You did not provide the command argument: `title: str`"
## Note
Needs Github API key

## Normal use
.config disable-extension [extension-name]
	Return a confrim embed "I've disabled that extension for this guild
## Expected errors
.config disable-extension [extension-name]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "I could not find that extension, or it's not loaded" if name does not exists
	Return a deny embed "That extension is already disabled for this guild" if extension is already disabled

## Normal use
.config enable-extension [extension-name]
	Return a confrim embed "I've enabled that extension for this guild" and enable the extension
## Expected errors
.config enable-extension [extension-name]
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "That extension is already enabled for this guild" If extension is already enabled
	Return a deny embed "I could not find that extension, or it's not loaded" if no extension exists

## Normal use
.config patch |uploaded-json|
	Return confim embed "I've updated that config"
.config patch
	Return the config file for the bot
## Expected errors
.config patch |uploaded-json|
	Return a deny embed "I couldn't match your upload data with the current config schema" if json is wrong

## Normal use
.raw |uploaded-python-file|
	Return a confrim embed "Code executed!" And execute the code in the file
## Expected errors
.raw
	Return a deny embed "No Python code found" if you do not provide a json
.raw |uploaded-python-file|
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a confrim embed "Code executed!" if file is a json
	Return a deny embed "Error: [e]" if it runs into an exception in the file

## Normal use
.listen clear
	Return a confrim embed "All listeners dergistered!
## Expected errors
.listen clear
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
## Note
Will return the confrim embed even if no jobs are cleared

## Normal use
.listen stop [src-channel] [dst-channel]
	Return a confim embed "Listening deregistered!"
## Expected errors
.listen stop [src-channel] [dst-channel]
	return a deny embed "Could not convert argument to: `<class 'cogs.listen.ListenChannel'>`" if [src-channel] or [dst-channel] is wrong
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
.listen stop
	Return a deny embed "You did not provide the command argument: `src: cogs.listen.ListenChannel`" if no src channel
.listen stop [src-channel]
	Return a deny embed "You did not provide the command argument: `dst: cogs.listen.ListenChannel` if no dest channel

## Normal use
.listen jobs
	Return an embed with the listener registrations with src and dest channels in description
## Expected errors
.listen jobs
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "There are currently no registered listeners" If not jobs exists

## Normal use
.listen start [src-channel] [dst-channel]
	Return a confrim embed "Listening registered!"
## Expected errors
.listen start [src-channel] [dst-channel]
	return a deny embed "Could not convert argument to: `<class 'cogs.listen.ListenChannel'>`" if [src-channel] or [dst-channel] is wrong
	Return a deny embed "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command." if not bot admin
	Return a deny embed "That source and destination already exist" if the listening config exists already
.listen start
	Return a deny embed "You did not provide the command argument: `src: cogs.listen.ListenChannel`" if no src channel
.listen start [src-channel]
	Return a deny embed "You did not provide the command argument: `dst: cogs.listen.ListenChannel` if no dest channel
