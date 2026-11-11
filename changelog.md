Changes since 2026.11.07

# Core
- Full migration of database engine from gino to piccolo
- UI.Confirm was rewritten to better support app commands

# Modules

## Administration

### Backup
- Removed, in favor of new DB_management commands

### Botinfo
- Redid the way the git version info is calculated

### DB_management
- New module, taking over backup. Allowing both exporting and importing of DB_management tables

### GitHub
- Full migration to app commands

## Fun

### Grabs
- Full migration to application commands

### Hangman
- Full migration to application commands
- Added ability to ban people from hangman

## Internal

## Moderation

### Featureban
- Added a new module to ban people from indiviual features

### Moderator
- Fixed edge case bugs when warning people causing the warn command to not work
- Warn modlogs now show total warnings after event
- Fixed edge case bug where a warn could be both applied and not applied at the same time

### Modmail
- Removed the invidiual ban commands in favor of a joint feature ban system.
- Made a new system for confirming new modmail threads

### Modlog
- Fixes edge case bugs if the moderator or member deleted their accounts
- Adds new channel field to all events

### Notes
- Note modlogs now show total notes after event
- Note modlogs now use the note as the reason instead of adding a different field

### Report
- Added ability to ban people from report

### Rules
- Full migration to application commands

## Operation

### Application
- Fixes edge case bug with unbanning someone from application
- Removed the individual ban commands in favor of a joint feature ban system.

### Factoid
- Fixes issue where factoid search breaks if factoids don't have an embed config

### Listen
- Migrate from BaseCog to MatchCog
- Full migraiton to application commands

### Modmail
- Fixes /modmail factoid not working after database changes

### Relay
- Full migration to application commands

## Utility

### ChatGPT
- Full migration to application commands

# Dependencies

## Core
- Regenerated the uv.lock file

## Prod
- Removed gino
- Removed setuptools
- Pinned Piccolo

## Dev

# Documentation
