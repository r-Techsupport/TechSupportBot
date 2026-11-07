Changes since 2026.06.15

# Core
- Create a new scheduling system, to replace LoopCog.

# Modules

## Administration

## Fun

### Giphy
- Fixes giphy command not correctly returning the image

## Internal

## Moderation

### Moderator
- Fix /mute command using the wrong datetime object

### Modlog
- Fix the data entry field for the automod block action type

### Nickname
- Fix config call missing guild ID

### Notes
- Fix clear note/note being wrong in modlog entries

### Report
- Fix report not working without a ping role configured

## Operation

### Factoid
- Complete migration to application commands
- Factoids are now allowed to use spaces
- /factoid add was renamed to /factoid create
- Fix permissions on /factoid create
- /factoid all has been reworked, is now always ephemeral
- /factoid all will now filter to only callable factoids, hiding disabled factoids, and hiding restricted factoids if not in a restricted channel
- /factoid call now works respects threads and restricted factoids
- /factoid call now works with IRC
- /factoid call now shows a "I see nothing" and "Save to DMs" button on factoids
- /factoid dealias now shows the remaining aliases on success

### Relay
- Make relay only ping users with words starting with an @

### XP
- Fix the /xp top command failing if someone has left the server

## Utility

# Dependencies

## Core
- Fix make sync command not installing the dev packages

## Prod
- apscheduler -> 3.11.3
- bidict -> 0.24.1
- cryptography -> 50.0.2
- dateparser -> 1.5.0
- emoji -> 2.16.0
- gitpython -> 3.2.1
- inflect -> 7.6.0

## Dev
- black -> 26.10.1
- flake8 -> 7.5.0
- flake8-annotations -> 3.3.1
- flake8-bugbear -> 26.10.27
- hypothesis -> 6.170.15
- isort -> 9.0.2
- pydoclint -> 0.12.0
- pylint -> 4.1.3
- pytest -> 9.2.0
- pytest-asyncio -> 1.4.1

# Documentation
