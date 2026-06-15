Changes since 2026.06.04

# Core
- A complete rework of the config system was been undertaken, replacing the database config system with a file based config system
- Restructures the file system to remove nesting everything in the "techsupport_bot" folder
- Restructions the extensions storage in the bot to be "modules.category.extension" instead of "commands.extension" or "functions.extension"
- Updates how module names are determined for application commands
- The presence intent is no longer requested
- Add property to make application commands always enabled regardless of guild config
- Adds a docker ignore file to slim down the size of the docker container
- Make the check-format make task run the same CI as is run on GitHub

# Modules

## Administration

### Bot info
- Full migration to application commands

### Echo
- Full migration to application commands

## Fun

### Animal
- Full migration to application commands
- Fixes the frog API to properly display images

### Burn
- Full migration to application commands

### Conch
- Full migration to application commands

### Correct
- Full migration to application commands

### Duck
- The default speed record is now -1
- Default speed record is now hidden from the UI in all cases
- Allow the .duck stats command to be run on a discord.User
- Changes the display of .duck stats to be a bit nicer
- Bot accounts are no longer able to participate in the duck hunt
- The caller of the .duck spawn command can no longer participate in the hunt
- Adds a new /duck next command to show admins the next duck spawn time
- Fuzzes duck spawn time to make it less predictable

### Grab
- Message content is now encrypted in the database

### Hangman
- /hangman start is no longer logged in discord

### XKCD
- Migrates to application commands

## Internal

### Data delete
- New module that has a command that allows users to delete some of their own data from the bot

### Privacy
- New module that adds a command to display the bots privacy policy to the user

## Moderation

### Events
- Complete overhaul of events logging system. A huge number of additional events are now tracked, and information is displayed in a more readable way

### Logger
- Now mentions roles instead of listing text names

### Moderator
- Adds autocomplete for /unwarn command
- Bans from max warnings will now show a ban in the text output

### Modmail
- Full migration to application commands
- The way modmail reads the configuration has changed to avoid the use of global variables
- Adds a command to send the text of a rule in a modmail thread
- Modmail was refactored to remove the usage of any privileged intents from the modmail bot itself
- Adds an edit button to messages

### Report
- The paramter name was changed from report_str to reason

### Role
- Adds a button to cancel editing roles

### Whois
- Now mentions roles in page 1, instead of listing text names
- Roles are now reveresed, to have the top role be listed first
- Will no longer display user status

## Operation

### Application
- Application will now display discord timestamps instead of plain text for pending application reminder loops

### Factoid
- The /factoid call command now has an optional parameter to ping a member in the factoid display
- Factoids called using /factoid call will now have a button to allow the invoker to delete the factoid
- A new /factoid add command has been added, using a modal to create new factoids
- Fix restricted factoids not working in threads

### Forum
- This changes the way the first message in a forum channel is obtained for initial post rejection detection
- This fixes initial detection for forums that first message have no content

### Relay
- Fixes SASL login issues, so the bot logs in using SASL now
- Properly checks if the channel the relay is configured for is configured for automod now

### XP
- A new /xp top command now exists, to display the top 10 XP members in the current guild

## Utility

### Dictionary
- New module, searches the Merriam-Webster Dictionary API for the passed word, and displays a definition

### Google
- This module was removed.
- Youtube was moved to a youtube module

### Help
- Reworks the way the help command displays usage info
- Mentions applications commands in the output now

### HTD
- Is more clear on what errors were caused and why
- Adds modulo as a valid operation

### Search
- Now uses application commands
- Now uses the Tavily API, to replace the deprcating google CSE API

### Weather
- Now uses application commands
- Has been rewritten to use the open-meteo API
- The UI has been reworked to be more information rich and better looking

### Youtube
- Now uses applications commands
- Is now a seperate file, having been decouping from the google extension

# Dependencies

## Core
- Python -> 3.13

## Prod
- Unpinned aiohttp
- Unpinned pips
- Unpinned pydantic
- Unpinned typing_extensions
- New dependency cryptograghy

## Dev
- hypothesis -> 6.155.2
- pylint -> 4.0.6
- pytest -> 9.1.0

# Documentation
Add detailed documentation for privileged intents usage
