# What is a cog
Cogs are application commands, prefix commands, or event listeners that are stored outside of the bot file.

In this project, there are two types of cogs: commands and functions.  
Commands are cogs that have either an application command or a prefix command.  
Functions are cogs that do not have any user commands. These can be loops or event listeners.

This split was done to make it more obvious where commands where located, improve generaton of help menus, and reduce confusion of the old names cogs and extensions.