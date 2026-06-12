# TechSupportBot Privacy Policy

**Last Updated: June 11, 2026**

## 1. Introduction
This Privacy Policy explains how TechSupportBot ("the Bot"), a self-hosted Discord bot operated by the r/TechSupport moderation team for the [r/TechSupport Discord server](https://discord.com/invite/2EDwzWa), collects, uses, stores, and deletes information about users who interact with it on Discord servers where the Bot is present. By using any server where TechSupportBot is active, you acknowledge the practices described here.

The Bot is self-hosted and operates exclusively within Discord in compliance with [Discord's Terms of Service](https://discord.com/terms), [Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy), and [Community Guidelines](https://discord.com/guidelines).

## 2. What Data We Collect
The Bot collects and stores the following categories of data in its PostgreSQL database and internal logs:

#### Moderation Records*
- **User IDs** of users who are warned, banned, kicked, muted, or unbanned
- **Warning records**: The warning reason, the issuing moderator's User ID, and the timestamp
- **Moderator notes**: free-text notes attached to a user by moderators, including the note body, the author's User ID, and timestamp
- **Ban logs**: the banned user's ID, the responsible moderator's ID, the ban reason, and the timestamp
- **Modmail ban records**: User IDs of users banned from using modmail

#### Modmail (Direct Message Relay)
- **All DMs sent to the modmail bot** are logged and relayed to a private moderation forum thread
- **Message contents and attachments** sent in modmail DMs are stored within forum threads
- **Thread metadata**: username, User ID, account creation date, join date, server nickname, roles, and past thread count are recorded on thread creation
- **Message edit history** in active modmail threads is logged

#### Activity and Event Logs
The bot logs the following Discord events internally to designated log channels:
- Message edits (before and after content, author, channel)
- Message deletions (message content, author, channel)
- Bulk message deletions
- Reaction additions and removals (emoji, user, message content)
- Member joins and leaves
- Member role changes
- Channel creation, deletion, and modification
- Guild (server) updates
- Role creation, deletion, and modification
- Command usage (author, channel, content up to 100 characters)

#### XP System
- **User ID** and **guild ID** paired with an integer XP value, updated whenever a qualifying message is sent

#### Applications
- **Application submissions** are stored in the database tied to the applicant's User ID

#### Duck Hunt (Fun Module)
- **User ID** and duck hunt statistics (kill/friend counts, speed records) stored per user

#### Grabs
- **User ID** and content of messages "grabbed" by moderators or other users

## 3. How We Use Your Data
Data is used solely for the legitimate operation of the server:
- **Moderation records** (warnings, bans, notes) are used by server moderators to maintain community safety and accountability
- **Modmail threads** allow users to privately contact the moderation team and allow staff to track conversation history
- **Event logs** are used by administrators to audit server activity and investigate incidents
- **XP data** is used to reward participation and assign XP-based roles
- **Application dat**a is used to process membership or role applications
- **Fun module data** (duck hunt, grabs) is used for community engagement features

We do not sell, share or transfer your data to any third parties.

## 4. Data Retention
- **Moderation records** (warnings, bans, notes, modmail bans) are retained indefinitely unless manually removed by a moderator or deleted by you via the `/data_delete` command (if you have administrator access to the Bot, otherwise please see section 5)
- **Ban logs** are retained indefinitely for moderation audit purposes
- **Modmail thread content** is archived (not deleted) when a thread is closed and remains in the modmail forum channel
- **Event logs** are sent to Discord log channels and subject to Discord's own message retention
- **XP, application, duck hunt, and grab data** are retained indefinitely until manually cleared or until you request deletion via `/data_delete` to the appropriate channel of communication

## 5. Your Rights and Data Deletion
You have the right to request deletion of certain personal data. The Bot provides a built-in `/data_delete` command that allows you to permanently and irreversibly delete:
- All submitted applications and their history
- Duck hunt participation records (speed records, kill/friend counts)
- All grabbed messages associated with your account
- Your XP data across all servers (including XP-based roles)

This action **cannot be undone**.

Data that cannot be self-deleted via this command includes:
- Moderation warnings, notes, and ban logs (these can be removed by a moderator upon reasonable request)
- Modmail thread content (as it forms part of the moderation record)

To request deletion of data not covered by `/data_delete`, contact the server moderation team via modmail (via Discord server or Reddit modmail).

## 6. Data Security
The Bot is self-hosted on infrastructure controlled by the r/TechSupport team. Data is stored in a PostgreSQL database accessible only to authorized server operators.

While most Bot functionality operates entirely within Discord, certain modules are capable of transmitting content to external third-party services:
- Paste module (currently active): May send message content to an external paste service when the `/paste` command is used
- Relay module (currently active): May relay message content to external services as part of its relay functionality

Outside of these specific features, no other data is transmitted to external third-party services beyond what is inherently required by Discord's API. Users should be aware that when interacting with these features, their content may leave Discord's infrastructure.

## 7. Data We Do Not Collect
The Bot does **not** collect:
- Real names, email addresses, IP addresses, or any information outside of Discord
- Messages that are not explicitly logged by the event system or passed through modmail
- Payment or financial information of any kind

## 8. Children's Privacy
The Bot does not knowingly collect data from users under the age of 13, consistent with Discord's minimum age requirement. If you believe a minor's data has been collected, please contact the moderation team (see section 5).

## 9. Changes to This Policy
 This Privacy Policy may be updated as the bot's features change. The "Last Updated" date at the top will reflect any revisions. Continued use of servers where the Bot is active constitutes acceptance of the current policy.

## 10. Contact
For questions, data requests, or concerns regarding this Privacy Policy, contact the r/TechSupport moderation team via the server or Reddit modmail system or through the project's [GitHub repository](https://github.com/r-Techsupport/TechSupportBot).