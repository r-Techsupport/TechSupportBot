Ignoring prefix commands, which are still heavily used by this bot, the bot uses the Message Content intent for the following reasons:

administration.listen
    This is a module designed to bridge two channels together across different guilds, though it can be used to bridge two channels in the same guild as well.

    This module sends this information into a discord channel in any guild, stores nothing on disk.

fun.autoreact
    This module monitors messages for specific keywords and automatically adds silly reactions to them. This is for the pure purpose of fun.

    This module does not send this information anywhere, nor does it store any information on disk.

fun.correct
    The correct command searches a channel for the most recent message matching a substring of content passed into it.
    The purpose of this command is to make fun social interactions.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

fun.duck
    The duck module runs a game of duckhunt in a configured channel, and part of the game is being the fastest at typing, including typos or having to decide to abandon the message you were typing.
    Due to the ideal design of the game, replacing this module with buttons will make it worse and less fun

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

fun.grab
    The grab command stores out of context messages by a specific author and allows them to be recalled at a later point in the future.

    This module sends this information into a discord channel in the same guild and stores the information in a database. Users have the capability of deleting their own information from the database.

fun.mock
    The mock command searchs the channel for the most recent message sent by a passed author. The bot will then send the message in a format like UdUdUdUd, for the purposes of being silly.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.automod
    This is a full automod implementation. Features strongly mirror those avaiable by the native discord automod, and those features will not be re-explained here. The following additional features are implemented:
        - The ability to send a publicly visible message in a channel when a message is sent matching content or regex. This is for the purposes of automatically warning our users of potentially malicious advice being given.
        - The ability to filter attachments based on file hash and/or file extension.
        - The ability to interact with our bots warning system
        - The ability to automatically kick or ban offending users
        - The ability to delete messages without user notification
    
    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.events
    This module tracks events such as message edit and delete events, for the purposes of enhancing moderation efforts.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.gate
    This is a custom rules gate, relying on having a user type a specific message into the chat to be granted an specific role.

    This module does not send this information anywhere, nor does it store any information on disk.

moderation.honeypot
    This is a module to create a honeypot, where should any messages be sent in the channel, users are automatically banned. Messages sent to this channel are logged for the purposes of building better automod rules in the future for the time in which the compromised account bots can avoid these types of channels.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

moderation.logger
    This module logs the content of all messages sent in given channels for the purposes of enhancing moderation efforts.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

operation.forum
    This module monitors for new threads created and checks the inital message against a set of rules. The explicit purpose of this is to close and lock threads that violate our rules, so they can be unlocked by our moderators for a false positive. We do not wish to block them from being sent entirely.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

operation.paste
    This module automatically deletes long messages and instead sends a link in the channel to a pastebin service.

    This module sends this information into a discord channel in the same guild, stores nothing on disk.

operation.relay
    This module is designed to bridge a discord channel to an irc channel. We use this to connect to our IRC channel ##techsupport.

    This module sends this information into a configured IRC channel. This stores nothing on disk.

operation.xp
    This module checks the content of the message to avoid giving XP to specific messages, with the purpose of preventing users from spamming our server.

    This module does not send this information anywhere, nor does it store any information on disk.
