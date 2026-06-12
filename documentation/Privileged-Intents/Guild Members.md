This bot will use the Guild Members intent for the following reasons

# moderation.events
## Module Explanation
This module tracks events across the entire guild, for the purposes of enhancing moderation and providing a more detailed, permanent audit log of events and changes to the guild. Logs are designed to be searched and referenced by moderators and admins days/weeks/months/years down the line.
## Intent Usage
The events module tracks changes to members, such as member joining and leaving, and select member update events.
## Video Demonstration
In the video moderation.events-guild_members_1.mov, you can see the events logging a member leaving and joining the guild.
## Data Handling
A message containing the member intent data may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.members
## Module Explanation
This module is designed to fetch every member with a passed role. This data is passed to the user in the form of a yaml file, with the purpose of being processed by the running moderator manually.
## Intent Usage
This module must fetch all members in a guild filtered by role in order to obtain this data and send it to the user.
## Video Demonstration
In the video moderation.members-guild_members_1.mov, you can see the members command being run to get all members with the ajax2-regular role, and then displaying that information in a yaml file.
## Data Handling
A message containing the list of members, IDs, names and role list, will be sent in the channel the command is run in. This will be in the same guild the member data is relevant for.<br>
While nothing is stored on disk by the bot, as a file is sent with this data, the intention is to have our moderators download the file and parse it using external tooling.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.modmail
## Module Explanation
This module contains a full modmail build, for full communication between users and moderators. This module manages modmails in a forum channel for the moderators side. Modmail will automatically send select events in the threads which our moderators ability to perform whatever is needed in modmail.
## Intent Usage
This module tracks members joining and leaving the server to send notice in the modmail thread that the member in the thread to alert staff of this important information.
## Video Demonstration
In the video moderation.modmail-guild_members_1.mov, you can see a modmail thread where the author of the thread leaves the guild, and then rejoins the guild shortly after. Notifications are sent in the modmail thread to alert staff.
## Data Handling
A message containing information about the user join/leaving the guild will be sent in the configured modmail channel.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.nickname
## Module Explanation
This modules enforces nickname rules on a guild. Nicknames are validated and changed on member join, on message, and manually by command
## Intent Usage
In order to change nicknames on joining the server, the module monitors member joins on the guild.
## Video Demonstration
In the video moderation.nickname-guild_members_1.mov, you can see the moderation.events logging system showing a member joining and then very shortly after joining, their nickname was changed. This is rather difficult to show in videos or screenshots otherwise, which is why moderation.events is used to show this in action.
## Data Handling
In the event the nickname was changed, the bot will DM the user who joined the guild to inform them their nickname was changed. While this message doesn't contain proof the user joined a specific guild, it would be very easy to work out the information by virtue of having the message at all.<br>
In the further event that the user has DMs turned off, a message will be sent in a bot logging channel configured by the guild informing staff that the user couldn't be notified, which would log a member join event in those cases.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.notes
## Module Explanation
This module allows moderators to set notes on users that the whole team can view. A notes role is applied to users who have notes, to let the staff team who has notes when looking at messages sent.
## Intent Usage
The bot will attempt to make this role "sticky", to auto apply the role on member joining. When a member joins, the bot looks in the database to see if any notes were set by staff previously. If so, the notes role is re-applied.
## Video Demonstration
In the video moderation.notes-guild_members_1.mov, you can see a member who has notes leaving and rejoining the server. Thanks to the moderation.events logging, you can see the member gets the ajax2-notes role upon joining.
## Data Handling
If the bot finds a user and re-applies the notes role, a log is sent in a configured log channel informing the staff such an action was taken. If no notes were found, this module will log nothing.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.forum
## Module Explanation
This module manages a forum channel for technical support purposes. With many features, such as auto locking threads after periods of inactivity, locking thread automatically if the OP leaves the server, preventing users from opening more than one thread, comparing new threads to a set of rules and auto locking threads that violate our rules, and many more.<br>
Threads being locked instead of just being closed or being fully deleted are a key feature of this module, as it allows staff to reopen threads if the automatic rules were wrong, but does not allow users to reopen their own threads.
## Intent Usage
The member remove event is monitored to check if a member has an open thread at the time they left. Closing the thread upon leaving helps prevent our staff from wasting time helping users who have left our server.
## Video Demonstration
In the video operation.forum-guild_members_1.mov, you can see a member who had created a forum has left the server. Upon leaving the server, the bot automatically comments in the thread, changes the title, and closes and locks the thread.
## Data Handling
A message containing information showing the user has left will be sent in the thread they opened.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.
