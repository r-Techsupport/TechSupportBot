Ignoring prefix commands, which are still heavily used by this bot, the bot uses the Message Content intent for the following reasons:

# administration.debug
## Usage
This module has a command to fetch and display every property of a collection of objects, including message (and message content)
## Purpose
The purpose of this module is to debug issues that happen with this bot, other bots, or native discord feature (like automod) when they happen in production
## Data Handling
This module is capable of accessing data across guilds, and will send a message containing the message content in the guild the command was run in.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# administration.listen
## Usage
This module is designed to bridge two differnet discord channels to each other, independent of the guild
## Purpose
The purpose of this module is to enable gross guild communication, to promote interactions with users that don't share a guild
## Data Handling
This module is capable of accessing data across guilds, and is designed to mirror message content from one guild to another, depending on setup and configuration.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.autoreact
## Usage
This module reacts configured reactions based on the given substring to search for
## Purpose
We search messages sent in the guild for any matching specific substrings as configured and add the relevant reactions to the message
## Data Handling
This data is not used in any permanent capacity. No messages are sent in any guild related to this module.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.correct
## Usage
This module contains a command that allows other users to "correct" a different message. The command then sends a correction replacing a passed substring with a new substring.
## Purpose
This module searches the channel the command was run in for a message containing the passed substring
## Data Handling
A message containing the partial content of the original message is sent in the same channel the original message was sent in. This is not capable of sending cross-guild messages.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.duck
## Usage
This modules runs a duckhunt game in a configured channel, with the goal being to have users type "bef" or "bang" to befriend or shoot the duck.
A core part of this game is supposed to be risking typos or not being able to participate if you were already typing a message.
## Purpose
This module monitors messages sent in the given channel and waits to see an appropriate message.
## Data Handling
While the message content is never sent anywhere directly, it is possible to rebuild the message content given how simple it is from a message the bot sends in the same channel declaring whether the user befriended or shot the duck.
The bot does not store any data related to this module permanently on disk, or in any external services. 
As above, no message content is not stored in the database directly, but the user ID is connected to how many ducks shot/befriended, making it possible to rebuild the message content of "bef" or "bang".
The data stored in the database by this module is capable of being deleted by the user, if desired.

# fun.grab
## Usage
This module allows users to grab out of context messages from a specific user, storing them to be recalled later.
## Purpose
This module has to read the message content of the message being grabbed in order to store the content for later use.
## Data Handling
Upon running the command, the bot will send a message containing the content in the same channel the command was run in. This will also be the same channel the message was sent in.
The bot does not store any data related to this module permanently on disk, or in any external services.
Message content will be stored in the datbase. Message content in the database may be accessed in any channel in the same guild, and by any user capable of running the relevant commands.
The data stored in the database by this module is capable of being deleted by the user, if desired.

# fun.mock
## Usage
This module has a command which finds the most recent message and sends in back in a format like "TeSt MeSsAgE hErE"
## Purpose
In order to show the mocked message, this module must be able to read the content of the message
## Data Handling
A message containing the edited content of the original message is sent in the same channel the original message was sent in. This is not capable of sending cross-guild messages.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.automod
## Usage
This module is a fully featured automod setup. It mirrors every feature the native discord automod has, which will not be re-detailed here. The additional features in which this module can do are as follows:
    - Rules based on attachments, including file extension and file hash based filter
    - The ability to send a message in the same channel the filtered message was detected in, visible to everyone.
    - The ability to kick and/or ban users who violate the automod rules
    - The ability to delete an offending message without any notice to the user
    - The ability to block based on pinging specific roles and/or users
    - The ability to exempt nobody from the filters
## Purpose
In order to run the additional automod capabilites as described above, the bot of course needs to be able to read the message content to determine what rule(s) to run
## Data Handling
A message containing the original message content may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.
The bot does not store any data related to this module permanently on disk or in any external services.
It is possible that the message content, or partial message content, may be stored in a database depending on configuration. Message content may be used as a warning reason.

# moderation.events
## Usage
This module tracks and logs a handful of events across the server, including some which will display message content.
Logs that include message content include, but are not limited to: message edits, message pins/unpins, message purge events.
## Purpose
These logs are designed to enhance moderation efforts. Many of the logs will be worse or completely pointless without message content.
## Data Handling
A message containing the original message content may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.gate
## Usage
This module is a custom rules gate that waits for a configured message to be sent in a configured channel. Upon detecting the correct message, a role will be applied to the author.
The bot automatically deletes all messages sent in this channel.
## Purpose
Message content is required to match the sent message to the configured message.
## Data Handling
No messages containing the content will be sent, but it will be possible to reverse engineer the message content sent by any user with the configured role, as the value will be known to everyone.
A self-deleting message confirming a user has passed the gate will be sent in the same channel as the user sent the message. This will not contain message content, but as above, it will be possible to reverse engineer the content of the message sent, as its a known value.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.honeypot
## Usage
This module automatically kicks any users who post a message in the configured honeypot channel.
All messages sent to this channel are logged to be reviewed and used as data to create better automod and anti-scammer/spammer rules going forward.
## Purpose
In order to enhance future moderation efforts and automated scammer/spammer removal, logging message content is essential to build effective future rules.
## Data Handling
A message containing the original content is sent in a configured channel, which is in the same guild as the original message was sent in.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.logger
## Usage
This module logs a carbon copy of all messages sent in a configured channel to a different channel.
## Purpose
The module logs message content with the purpose of enhancing moderation efforts, allowing mods to look up messages of users, especially those purged by someone being banned, at an arbitrary time in the future.
## Data Handling
A message containing the original content is sent in a configured channel, which is in the same guild as the original message was sent in.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.forum
## Usage
This module monitors new threads being created in a configured forum channel. The message content of the original message is compared to a set of rules.
Should the thread violate our rules, the module locks and closes the thread.
## Purpose
We use the message content to determine if the threads violate our rules. The goal of this is not to block the message or delete the thread, as to allow moderators to decide a false positive and unlock and reopen the thread.
## Data Handling
A message is sent to the same thread the original message was sent in explaing the thread violated our rules, but no part of the message content is sent there, or anywhere.
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.paste
## Usage
This module monitors sent messages in configured channels for messages that are too long. Messages that are too long are deleted and the bot will send a link to a paste service containing the message.
## Purpose
The message content is used to determine if the message is long enough to qualify for being pasted, based on the configured limit.
## Data Handling
A message is sent in the same channel as the original message containing partial message content. Any attachments in the original message will be reuploaded.
The full message content text is sent to a configured paste service. A link to this paste service is sent in the same channel as the original message.
The bot does not store any data related to this module permanently on disk or in any databases.

# operation.relay
## Usage
This module is designed to bridge and IRC and discord channel together, to allow cross platform communication and engagement.
## Purpose
Message content is read and sent to IRC, as to allow users on IRC to read what people on discord have said.
## Data Handling
No messages containing the message content will be sent in any channel on discord.
The full message content of the message will be sent to a configured IRC channel.
The bot does not store any data related to this module permanently on disk or in any databases.

# operation.xp
## Usage
This module monitors messages in configured channels to assign XP for activity.
## Purpose
We use the message content to compared against rules to detect spam messages, as to disuade users from spamming our server.
## Data Handling
This data is not used in any permanent capacity. No messages are sent in any guild related to this module.
The bot does not store any data related to this module permanently on disk, or in any external services.
XP data is stored in our database, though message content or any way of determing message content is not.
The data stored in the database by this module is capable of being deleted by the user, if desired.


# For complete documentation, the following modules are currently using prefix commands:
- Administration: administration.commandcontrol, administration.echo, administration.embed, administration.github, administration.leave, administration.listen, administration.restart, administration.set, administration.sync
- Moderation: moderation.gate, moderation.members, moderation.rules
- Fun: fun.duck, fun.emoji, fun.giphy, fun.grab, fun.hangman, fun.hug, fun.kanye, fun.joke, fun.lenny, fun.mock, fun.roll, fun.wyr
- Operation: operation.factoid, operation.relay
- Utility: utility.chatgpt, utility.dumpdbg, utility.help, utility.htd, utility.ipinfo, utility.iss, utility.linter, utility.poll, utility.spotify, utility.translate, utility.urban, utility.wolfram
