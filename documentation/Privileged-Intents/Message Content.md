Ignoring prefix commands, which are still heavily used by this bot, the bot uses the Message Content intent for the following reasons:

# administration.debug
## Module Explanation
This module exists to allow debugging of events by displaying all properties of given discord objects, such as channels, messages and members. This helps fix bugs in the code, solve why scammers are bypassing automod rules, etc.
## Intent Usage
This module uses the Message Content intent when dispalying properties of messages. While this is just one of the many properties displayed, message content is helpful, especially with fixing issues with native automod rules.
## Video Demonstration
In the video administration.debug-message_content_1.mov, you can see the command `/debug message` being ran, and displaying all the properties of the message sent in the channel
## Data Handling
This module is capable of accessing data across guilds, and will send a message containing the message content in the guild the command was run in.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# administration.listen
## Module Explanation
This module is designed to bridge two differnet discord channels to each other, independent of the guild. All messages sent in any one channel are mirrored to the second channel. The goal of this module is to enable cross-guild interactions
## Intent Usage
This module uses the Message Content intent when forwarding messages between channels. In order to forward the messages between channels access to the message content is essential.
## Video Demonstration
In the video administration.listen-message_content_1.mov, you can see me sending a message in the channel, and then later the bot sending a message from the #dev-only channel in a differnet guild.<br>
In the screenshot administration.listen-message_content_2.png, you can see the other end of this link, having recieved the first message from the original guild, and having send the second message in that guild.
## Data Handling
Full message content of all messages sent in configured channels will be copied to the other channel, which may be in an arbitrary guild.<br>
This module is capable of accessing data across guilds, and is designed to mirror message content from one guild to another, depending on setup and configuration.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.autoreact
## Module Explanation
This module searches for substrings having been sent in a configured guild. If those substrings have been detected in a sent message, the bot will add a configured reaction automatically.
## Intent Usage
This module reads all messages sent in the guild and searches the content for a configured list of substrings. In order to determine if a reaction should be added, the message content must be accessed.
## Video Demonstration
In the video fun.autoreact-message_content_1.mov, you can see me sending two messages. Only one of which gets a configured autoreaction. I show the bot having been the account which reacted to the message.
## Data Handling
The message content data used by this module is entirely processed in memory.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.correct
## Module Explanation
This module contains a command that allows other users to "correct" a different message. The command then sends a correction replacing a passed substring with a new substring.
## Intent Usage
This module searches the channel the command was run in for a message that contains the passed substring.<br>This moudle also uses the message content to replace the substring with the new string, and display the corrected message to the users.
## Video Demonstration
In the video fun.correct-message_content_1.mov, you can see a different user sending a message in the channel, and then me running the `/correct` command, where the bot responds with the original message having the word "word" replaced with the word "different"
## Data Handling
A message containing the partial content of the original message is sent in the same channel the original message was sent in.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# fun.duck
## Module Explanation
This module starts a game of duckhunt randomly in configured channels. Upon starting, a message will be sent in the channel telling users they have to type "bang" to shoot the duck or "bef" to befriend the duck. Its a race to type the message first, without any typos.<br>
A part of the challenge is being able to type fast. Another part of the challenge is having to decide to finish typing a message you were already typing or throwing it away and replacing it with "bef" or "bang".
## Intent Usage
While the game of duckhunt is running, this module compares all messages sent in the relevant channel and checks if they are valid message, either "bef" or "bang".
## Video Demonstration
In the video fun.duck-message_content_1.mov, you can see a user participating in the duck hunt game, and making a typo before shooting the duck and having the session of the game end.<br>
Due to the nature of making this demonstration, the command "duck spawn" was used to start the game. The game starts randomly in configured channels making getting a video like this rather difficult.
## Data Handling
While the message content is never sent anywhere directly, it is possible to rebuild the message content given how simple it is from a message the bot sends in the same channel declaring whether the user befriended or shot the duck.<br>
The bot does not store any data related to this module permanently on disk, or in any external services. <br>
As above, no message content is not stored in the database directly, but the user ID is connected to how many ducks shot/befriended, making it possible to rebuild the message content of "bef" or "bang".<br>
The data stored in the database by this module is capable of being deleted by the user, if desired.

# fun.grab
## Module Explanation
This module allows users to save a message that was sent by a different user. The messages that were grabbed are capable of being recalled at future points. The purpose of this module is to save and recall out of context quotes.
## Intent Usage
This module reads the message content of the most recent message a given user has sent in the channel the command was run in. The content of the message is read and saved in the database.
## Video Demonstration
In the video fun.grab-message_content_1.mov, you can see another user sending 2 message in the channel, and me grabbing each one and demonstrating the grab command to store the message, and the grabs all command to fetch the stored messages.
## Data Handling
Upon running the command, the bot will send a message containing the content in the same channel the command was run in. This will also be the same channel the message was sent in.<br>
The bot does not store any data related to this module permanently on disk, or in any external services.<br>
Message content will be stored in the database. Message content in the database may be accessed in any channel in the same guild, and by any user capable of running the relevant commands.<br>
The data stored in the database by this module is capable of being deleted by the user, if desired.

# fun.mock
## Module Explanation
This module is designed to find and alter a message of a given user in a format like "TeSt MeSsAgE hErE". The bot will send the altered message back in the channel the command was sent in.
## Intent Usage
This module must read the content of the message in order to edit the message for its new display.
## Video Demonstration
In the video fun.mock-message_content_1.mov, you can see another users message in the channel, and watch me run the mock command on the other user.
## Data Handling
A message containing the edited content of the original message is sent in the same channel the original message was sent in.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.automod
## Module Explanation
This module is a fully featured automod setup. It mirrors every feature the native discord automod has, which will not be re-detailed here. The additional features which this module implements are as follows:
- The ability to filter attachments based on file extension
- The ability to filter attachments based on file hash
- The ability to send a message in the same channel the filtered message was detected in, visible to everyone.
- The ability to kick and/or ban users who violate the automod rules
- The ability to delete an offending message without any notice to the user
- The ability to block based on pinging specific roles and/or users
- The ability to exempt nobody from the filters
- The ability to apply our bots warnings to users
- The ability to mute users for an arbitrary amount of time (or at least 1 second to 28 days, as restricted by the API)
## Intent Usage
This module reads all of the message content in order to determine if the message is in violate of any of the configured automod rules.
## Video Demonstration
In the video moderation.automod-message_content_1.mov you can see a demonstration of 4 different features of the automod. Starting with a public notice having been sent, visible to everyone. Then a message that will be silently deleted. Then a message triggering a custom 17 second mute. Then finally a message containing a txt file extension, which was blocked in this example.
## Data Handling
A message containing the original message content may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.<br>
The bot does not store any data related to this module permanently on disk or in any external services.<br>
It is possible that the message content, or partial message content, may be stored in a database depending on configuration. Message content may be used as a warning reason.

# moderation.events
## Module Explanation
This module tracks events across the entire guild, for the purposes of enhancing moderation and providing a more detailed, permanent audit log of events and changes to the guild. Logs are designed to be searched and referenced by moderators and admins days/weeks/months/years down the line.
## Intent Usage
Many of the events logged are related to message/message content, and display message content in the logs. These events include but are not limited to: Message edits, message pins, message deletes.
## Video Demonstration
In the video moderation.events-message_content_1.mov, you can see a demonstration of the content being displayed in logs for the events of message editing, message pinning, and message deleting.
## Data Handling
A message containing the original message content may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.gate
## Module Explanation
This module is a custom rules gate that waits for a configured message to be sent in a configured channel. Upon detecting the correct message, a role will be applied to the author.<br>
The bot automatically deletes all messages sent in this channel.
## Intent Usage
This module must read message content to determine if the message sent matches the configured message to pass the rules gate.
## Video Demonstration
In the video moderation.gate-message_content_1.mov, you can see a user sending 2 messages in the server gate channel. One is deleted and nothing happens, as its not the correct message. The other message is the correct message and it does show the gate success message.
## Data Handling
No messages containing the content will be sent, but it will be possible to reverse engineer the message content sent by any user with the configured role, as the value will be known to everyone.<br>
A self-deleting message confirming a user has passed the gate will be sent in the same channel as the user sent the message. This will not contain message content, but as above, it will be possible to reverse engineer the content of the message sent, as its a known value.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.honeypot
## Module Explanation
This module automatically kicks any users who post a message in the configured honeypot channel.<br>
All messages sent to this channel are logged to be reviewed and used as data to create better automod and anti-scammer/spammer rules going forward.
## Intent Usage
In order to enhance future moderation efforts and automated scammer/spammer removal, logging message content is essential to build effective future rules.
## Video Demonstration
In the video moderation.honeypot-message_content_1.mov, you can see a user send a message in the honeypot channel. After the message is sent you can see the honeypot log also being sent in the same channel.
## Data Handling
A message containing the original content is sent in a configured channel, which is in the same guild as the original message was sent in.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.logger
## Module Explanation
This module is designed to create an immutable copy of a channel, for future reference by staff. All messages sent in configured channels will be copied, in a way designed to be searched in the future.
## Intent Usage
The module logs message content, along with more information about the message, channel, and author.
## Video Demonstration
In the video moderation.logger-message_content_1.mov, you can see two messages having been logged after being sent in a different channel.
## Data Handling
A message containing the original content is sent in a configured channel, which is in the same guild as the original message was sent in.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.forum
## Module Explanation
This module manages a forum channel for technical support purposes. With many features, such as auto locking threads after periods of inactivity, locking thread automatically if the OP leaves the server, preventing users from opening more than one thread, comparing new threads to a set of rules and auto locking threads that violate our rules, and many more.<br>
Threads being locked instead of just being closed or being fully deleted are a key feature of this module, as it allows staff to reopen threads if the automatic rules were wrong, but does not allow users to reopen their own threads.
## Intent Usage
The message content of the original message of new threads is the only times message content is accessed. Message content is used to compared against regex and content filters to automatically lock threads that violate the given rules.
## Video Demonstration
In the video operation.forum-message_content_1.mov, you can see me creating a new thread and having the bot automatically reject it based on the word "banned" being filtered. You can then watch me run the reopen command to unlock and rename the thread.
## Data Handling
A message is sent to the same thread the original message was sent in explaing the thread violated our rules, but no part of the message content is sent there, or anywhere.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.paste
## Module Explanation
This module monitors sent messages in configured channels for messages that are too long. Messages that are too long are deleted and the bot will send a link to a paste service containing the message.
## Intent Usage
The message content is used to determine if the message is long enough to qualify for being pasted, based on the configured limit. The message content is also used as the content in the paste.
## Video Demonstration
In the video operation.paste-message_content_1.mov, you can watch a user post a very long message in a configured channel, and a few seconds later the bot will delete the message and link to a paste link instead.
## Data Handling
A message is sent in the same channel as the original message containing partial message content. Any attachments in the original message will be reuploaded.<br>
The full message content text is sent to a configured paste service. A link to this paste service is sent in the same channel as the original message.<br>
The bot does not store any data related to this module permanently on disk or in any databases.

# operation.relay
## Module Explanation
This module bridges an IRC channel and discord channel together. Its purpose is to enable cross platform communication.
## Intent Usage
In order to bridge messages between the platforms, content of all messages sent must be read and sent to IRC.
## Video Demonstration
In the video operation.relay-message_content_1.mov, you can see an IRC user's message being forwarded to the discord channel, and watch me type a message in the discord channel.<br>
In the screenshot operation.relay-message_content_2.png, you can see the IRC side, where the message sent on IRC is first and you can the forwarded discord message.
## Data Handling
No messages containing the message content will be sent in any channel on discord.<br>
The full message content of the message will be sent to a configured IRC channel.<br>
The bot does not store any data related to this module permanently on disk or in any databases.

# operation.xp
## Module Explanation
This module monitors messages sent in configured channels, runs some anti-spam checks on the message. If the message passes our anti-spam checks, a random amount of XP is assgined to a user.<br>
Users who earn enough XP are given activity based roles, or have their activity based role modified.
## Intent Usage
Some of the anti-spam checks this module includes some message length and message content rules, as such message content is used as part of these anti-spam checks.
## Video Demonstration
As this module does not display this data to the user in any capacity, log anything anywhere, store this data in the database, or otherwise make it visible that this data is being used, no video is capable of being made.
## Data Handling
This data is not used in any permanent capacity. No messages are sent in any guild related to this module.<br>
The bot does not store any data related to this module permanently on disk, or in any external services.<br>
XP data is stored in our database, though message content or any way of determing message content is not.<br>
The data stored in the database by this module is capable of being deleted by the user, if desired.


# Prefix commands
For complete documentation, the following modules are currently using prefix commands, and subsequently require message content until migration is complete:
- Administration: administration.commandcontrol, administration.echo, administration.embed, administration.github, administration.leave, administration.listen, administration.restart, administration.set, administration.sync
- Moderation: moderation.gate, moderation.members, moderation.rules
- Fun: fun.duck, fun.emoji, fun.giphy, fun.grab, fun.hangman, fun.hug, fun.kanye, fun.joke, fun.lenny, fun.mock, fun.roll, fun.wyr
- Operation: operation.factoid, operation.relay
- Utility: utility.chatgpt, utility.dumpdbg, utility.help, utility.htd, utility.ipinfo, utility.iss, utility.linter, utility.poll, utility.spotify, utility.translate, utility.urban, utility.wolfram
