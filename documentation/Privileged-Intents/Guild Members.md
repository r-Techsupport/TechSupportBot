This bot will use the Guild Members intent for the following reasons

# moderation.events
## Usage
This module tracks and logs a handful of events across the server, including member joins, edits, and leaves.<br>
Logs that include privileged member info include, but are not limited to: member joins, nickname edits, and member remove.
## Purpose
These logs are designed to enhance moderation efforts. Many logs that our moderators rely on will not be able to be sent.
## Data Handling
A message containing the member intent data may be sent to an arbitrary channel in the same guild, which may or may not be the same channel the message was originally sent.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.members
## Usage
A module desgined to enhance moderation efforts, this allows our moderators to get a yaml file of all members in the guild with a given role
## Purpose
In order to get all the members with a specific role, access to guild.members is requied
## Data Handling
A message containing the list of members, IDs, names and role list, will be sent in the channel the command is run in. This will be in the same guild the member data is relevant for.<br>
While nothing is stored on disk by the bot, as a file is sent with this data, the intention is to have our moderators download the file and parse it using external tooling.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.modmail
## Usage
This module alerts our staff if someone who has opened a modmail ticket with us has left or re-joined the server
## Purpose
In order to send these alerts, this module must track members joining and leaving
## Data Handling
A message containing information about the user join/leaving the guild will be sent in the configured modmail channel.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.nickname
## Usage
This module is designed to enforce our nickname rules on members when they join our server.
## Purpose
In order to change nicknames on joining the server, the module member joins on the guild.
## Data Handling
In the event the nickname was changed, the bot will DM the user who joined the guild to inform them their nickname was changed. While this message doesn't contain proof the user joined a specific guild, it would be very easy to work out the information by virtue of having the message at all.<br>
In the further event that the user has DMs turned off, a message will be sent in a bot logging channel configured by the guild informing staff that the user couldn't be notified, which would log a member join event in those cases.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# moderation.notes
## Usage
This module allows moderators to set notes on users that the whole team can view. A notes role is applied to users who have notes, to let the staff team who has notes when looking at messages sent.
## Purpose
The bot will attempt to make this role "sticky", to auto apply the role on member joining. When a member joins, the bot looks in the database to see if any notes were set by staff previously. If so, the notes role is re-applied.<br>
## Data Handling
If the bot finds a user and re-applies the notes role, a log is sent in a configured log channel informing the staff such an action was taken. If no notes were found, this module will log nothing.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.

# operation.forum
## Usage
This modules auto closes any open threads in a configured forum channel if the OP of the thread leaves the guild.
## Purpose
The member remove is monitored to check if a member has an open thread at the time they left. Closing the thread upon leaving helps prevent our staff from wasting time helping users who have left our server.
## Data Handling
A message containing information showing the user has left will be sent in the thread they opened.<br>
The bot does not store any data related to this module permanently on disk, in any databases, or in any external services.
