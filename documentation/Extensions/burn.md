# Burn extension
The burn extension has no config, no databases, and no API.  

## Dependencies
This file uses discord.py

## Commands
There is a single command in this extension, `.burn`.

### .burn
This command takes a single argument, a user.  
Running this command will mention the user and react to the most recent message

#### Errors
Running the command without proper permissions will send a deny embed that says "I ran into an error processing your command: You are missing Bot Admin permission(s) to run this command."
