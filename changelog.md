Changes since 2026.11.07

# Core
- Full migration of database engine from gino to piccolo

# Modules

## Administration

### Backup
- Removed, in favor of new DB_management commands

### DB_management
- New module, taking over backup. Allowing both exporting and importing of DB_management tables

## Fun

### Grabs
- Full migration to application commands

## Internal

## Moderation

### Rules
- Full migration to application commands

## Operation

### Application
- Fixes edge case bug with unbanning someone from application

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

# Dependencies

## Core
- Regenerated the uv.lock file

## Prod
- Removed gino
- Removed setuptools
- Pinned Piccolo

## Dev

# Documentation
