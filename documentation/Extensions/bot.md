# Bot extension
The bot extension has no config, no databases, and no API.  

## Config
This extension reads the file_config.api.irc.enable_irc.  
No guild config or environment variables are read by this extension.  

## Dependencies
This file uses discord.py and gitpython

## Commands
There is a single command in this extension, `.bot`.

### .bot
This command takes no arguments and requires bot admin permissions.  
Upon running the command, it will output an embed with various information such as github version, irc information, and latency.

#### Errors
Running the command without proper permissions will send a deny embed that says "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command."
