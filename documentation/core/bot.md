# Documentation for functions in the bot.py file
The bot.py file is the primary file of the program. It contains all of the core functions responsible for loading the bot, config, irc, and extensions. This is the entry point from the main.py file

## __init__:

## Entry point

### start:

## Discord.py called functions

### setup_hook

### cleanup

### on_guild_join

### can_run

### on_ready

### on_message

## Guild config management functions

### register_new_guild_config

### create_new_context_config

### write_new_config

### add_extension_config

### get_log_channel_from_guild

## File config loading functions

### load_file_config

### validate_bot_config_subsection

## Error handling and logging functions

### on_app_command_error

### handle_error

### on_command_error

## Postgres setup functions

### generate_db_url

### get_postgres_ref

## Extension loading and management functions

### get_potential_extensions

### get_potential_function_extensions

### load_extensions

### get_command_extension_name

### register_file_extension

## Bot properties

### is_bot_admin

### get_owner

### startup_time

### get_prefix

## Other stuff

### slash_command_log

### start_irc
