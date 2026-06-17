Changes since 2026.06.15

# Core
- Create a new scheduling system, to replace LoopCog.

# Modules

## Administration

## Fun

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

## Utility

# Dependencies

## Core

## Prod

## Dev

# Documentation
