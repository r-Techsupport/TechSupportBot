# The (command/function) development guide
The purpose of this document is to highlight how common things you will need to interact with during modification or creation of extensions of the bot.  
This is mainly focused on extensions, but parts of this can be reused in core development as well.  
In this document, commands and functions are referred to as collective extensions. See Cog Types.md to determine if you need to make a command or a function.

## Basic extension setup
Creating the most basic extension layout requires 3 things:
- importing cogs
- a setup function that loads the cog
- a class inheriting from the base cog

These three things must be present, or expanded upon, for your extension to work.
Here is an example:
```py
from core import cogs

async def setup(bot):
    await bot.add_cog(ExtensionName(bot=bot))

class ExtensionName(cogs.BaseCog):
    ...
```
Ensure that your extension class name is globally unique, otherwise you will have problems loading your extension, or will break another existing extension.  
From here, you are able to add anything to your extension, it will get automatically loaded with the name of the extension matching that of the file name.

## Preconfig
Preconfig is run once when the bot is setting up the extension. It is guaranteed that this function will not be called before the bot has completely loaded.  
This function should be used to setup any variables or tasks that are not guild specific, such as setting default variables or starting custom jobs.  
A preconfig function is optional, if you do not include it nothing will be done.  
Here is an example (example code from commands/role.py):
```py
async def preconfig(self):
    self.locked = set()
```
This function can take no arguments and anything returned will not be able to be used anywhere

## Creating a new table or modifying an existing table in postgres
Creating a new table in postgres takes place in core/databases.py.  
Inside of this file is where all of the tables are defined and loaded into the bot.  
You can modify any existing table here, and the docstrings in the table classes let you know where that table is used so you can make appropriate changes everywhere.  
In order to create a column in a table, you require:
- A locally uniuqe name. The variable name will be the column name.
- A variable type  
Here is an example column (example code from the listen database):
```py
src_id = bot.db.Column(bot.db.String)
```
Do not edit the `bot.db.Column` section.  
Some valid datatypes are:  
bot.db.Integer, bot.db.String, bot.db.DateTime, bot.db.Boolean, bot.db.Float  
**Modifications to tables will NOT be done automatically. You must modify the database manually or drop the table and have it be recreated without any data.**

To create a new table, you must have the following:
- A table name. This must be globally unique.
- An Integer primary key
- At least one not primary key entry. The primary key can be named anything.  
Here is an example (example from from the rule database):
```py
class Rule(bot.db.Model):
    __tablename__ = "guild_rules"
    pk = bot.db.Column(bot.db.Integer, primary_key=True)
    guild_id = bot.db.Column(bot.db.String)
```
It is mandatory that your table name doesn't contain spaces.  
It is recommended that your table name is all lowercase.  

You can assign default values to your columns, like so (example from grabs):
```py
nsfw = bot.db.Column(bot.db.Boolean, default=False)
```
These will not be retroactivly assigned to existing rows in the database, but will be added to all new rows that don't specify a value

Additionally, in order to make your table accessible, you must add it to the bot.models dict at the bottom of the file.  
Failing to do this will still cause your table to be created, but it will not be accessible.  
Here is an example (example from applications):
```py
bot.models.Applications = Applications
```
You do not have to match the name in the models, however it is recommended you do.

### Foreign Key


## Reading data from postgres
Disclaimer: gino is a massive library, there are dozens more ways to interact with the database than are listed here or used anywhere in this code. This is not a definitive guide of what you are allowed to use, but rather a summary of what we currently use.

You can access a specific table by calling `bot.models.TableClassName`.

There are two ways to get data from the database:
- gino.first()
- gino.all()

gino.first() will return the first matching entry in the database, as a database object.  
gino.all() will return a list of all matching queries, or an empty list. The list will be of database objects.

A query is made up of 3 components:
- The table you would like to query
- The conditions you are filtering for
- The amount of entries you want back

The table is very simple to get, by using the above `bot.models.TableClassName`. This can be accessed anywhere you have the bot object accessible to you.  
Following that, you need to add `.query` and `.where()`. The query line is mandatory, but if you don't want to filter the output at all, you can omit the where.  
Finally, you need to end your query with `.gino.first()` or `.gino.all()`. These are async functions and will require to be called with await.  

If you desire, you can omit the `.gino.first()` or `.gino.all()` and just build a query object without actually calling the database. You will need to call `.gino.first()` or `.gino.all()` on the query object you made later

### Query and where usage
The most basic query is one without any where statements. This will search the entire database, and either return all or the first. Example (from bot.py):
```py
all_config = await self.models.Config.query.gino.all()
```
This will get all entries from the Config database and return it as a list.  

A more complex query is one where you need to use the `.where()` clause to filter your output. Filtering the output is based on the column name you want to filter. You can stack as many filters on a single query, by just stacking `.where()`. Here is a simple example (from commands/factoids.py):
```py
jobs = await self.bot.models.FactoidJob.query.where(
    self.bot.models.FactoidJob.factoid == factoid.factoid_id
).gino.all()
```
This will return a list of all entries in the FactoidJob database, where the factoid column matches `factoid.factoid_id`.  
If you wish to stack queries, you can do that as well. There is no limit to how much you can stack. Here is an example (from commands/application.py):
```py
query = (
    self.bot.models.Applications.query.where(
        self.bot.models.Applications.applicant_id == str(member.id)
    )
    .where(self.bot.models.Applications.guild_id == str(member.guild.id))
    .where(
        self.bot.models.Applications.application_stauts
        == ApplicationStatus.PENDING.value
    )
)
entry = await query.gino.first()
```
This is creating a query and calling it separatly.  
The query is searching the Applications table for a specific application with a status of pending, made by a specific user, in a specific guild. The `gino.first()` means it will only return a single entry

### Order by
There may be a time you wish to order your results by something othe than the primary key. If this is the case, you can add `.order_by()` to your database query. The placement of this must be after the `.query` term, but can be in any relation to the `.where()` terms. You can use any column from the table to sort by. Here is an example (from commands/who.py):
```py
user_notes = (
    await self.bot.models.UserNote.query.where(
        self.bot.models.UserNote.user_id == str(user.id)
    )
    .where(self.bot.models.UserNote.guild_id == str(guild.id))
    .order_by(self.bot.models.UserNote.updated.desc())
    .gino.all()
)
```
This is sorting in a descending order by the updated column.

## Modifying data from postgres

## HTTP Calls
Extensions requiring the use of an API will require you to make an HTTP call. There is an async HTTP function built into the bot ready for you to use. 

In order to access this function, all you need to do is call it using the `bot` object (example from cat.py):
```py
await self.bot.http_functions.http_call("get", url)
```
You can use both a get and post call with this function. And you can pass any arguments by any name. Here is a more complex example from spotify.py:
```py
response = await self.bot.http_functions.http_call(
    "post",
    self.AUTH_URL,
    data=data,
    auth=aiohttp.BasicAuth(
        self.bot.file_config.api.api_keys.spotify_client,
        self.bot.file_config.api.api_keys.spotify_key,
    ),
)
```

This will return a munch dictionary. If you have a need for the raw response, you are able to get that by adding a get_raw_response parameter. Example from wolfram.py:
```py
response = await self.bot.http_functions.http_call(
    "get", url, get_raw_response=True
)
```

To avoid hanging the bot, do not use any other http call function, as these may hold up anything from happening on the bot until the call has finished.  
When adding a new API to the bot, you should add a rate limit to the API by editing core/http.py. Add a new entry in the `rate_limits` dict. Put the base URL with a tuple of (calls, seconds). 


## Error handling
Any errors raised by you or a library you are using raises will be handled by a central error handler.  
If you don't want the command to abort or have some other custom handling, a try/except statement is what you want. Avoid using a bare except or a generic except. Catching specific errors is good practice and avoids hiding bugs that will later show up and be hard to find.  
An error should always mean that something went wrong, and that whatever function or command you are running is not recoverable.

### Making custom errors
Custom errors can allow you to have custom output by the default error handler, ensuring more consistency and allowing you to tell the user what they need to know. Custom errors are defined in `core/custom_errors.py`.  
To make a custom error, you need to make a class that inherits from a command or app_command error, depending on if you will be raising it from a prefix or app command.  
Here is some example code (from the http rate limit error):
```py
class HTTPRateLimit(commands.errors.CommandError):
    """An API call is on rate limit"""

    def __init__(self, wait):
        self.wait = wait
```
This error inherits from commands.errors, so it will only work correct if called from a prefix command. If called from an application command, the error will be displayed on in the console with no special user side handling

In these errors, you can define as many properties as you would like, with any names. In the example above, there is a wait variable, which is supposed to indicate how long a user must wait before using a given API again.  
You can define a special property, `self.dont_print_trace`, for the errors that don't need a stack trace printed. Use this cautiously and only when you are sure that the stack trace will provide zero useful information. This option will prevent the stack trace from being sent anywhere, **including the console**.

You can additionally have custom output for these errors, by adding an entry to the COMMAND_ERROR_RESPONSES array, in the `core/custom_errors.py` file. Here are some examples:
```py
HTTPRateLimit: ErrorResponse(
    "That API is on cooldown. Try again in %.2f seconds",
    {"key": "wait"},
),
ExtensionDisabled: ErrorResponse(
    "That extension is disabled for this context/server"
),
```
These errors are formatted using the printf strings, and a key that points back to the custom variables defined in your error class.  
After these two, when you want to raise your error, you need to import the custom errors class from core:
```py
from core import custom_errors
raise custom_errors.HTTPRateLimit(4.5)
raise custom_errors.ExtensionDisabled
```

## Creating slash commands
In order to create a slash command, you need to import the app commands features from discord.py.
```py
from discord import app_commands
```

Then, inside of the command class, add the following decorator to a function:
```py
@app_commands.command(
        name="NAME",
        description="DESC",
        extras={"module": "MODULE_NAME"},
    )
async def command(self, interaction: discord.Interaction)
```
The function must take an argument of the discord interaction.
This will make a command `/NAME` avaiable, and it will be enabled if the extras module name is marked as enabled in the guild.

In order to make a command group, you can do this:
```py
role_group = app_commands.Group(name="role", description="...")
```
This will create a group with a name, so all commands in that group will be under `/role command`
In order to use this group, use the same thing as above, but replace `@app_commands` with the name of your group, `@role_group`

## Creating context menu entires

## Creating prefix commands

## Context vs interaction

## Responding to the user

## Creating custom embeds

## Pagination

## Confirmation
The ui module provide a library for having the user confirm some action. This will provide the user a prompt and request they select a confirm or cancel option.  
The buttons in this library will stop working in the event the bot gets restarted, so there will be no phantom inputs from the view.  
There are three possible outcomes from the confirmation, defined in the ConfirmResponse enum:
- The user confirmed (CONFIRMED)
- The user denied (DENIED)
- No options were selected within 1 minute (TIMEOUT)

You will have to import the ui package in order to use the confirmation function. This confirmation system is avaiable to both prefix commands and app commands. The confirmation package does no lock or collision checking, any error handling based on 2 events to the same item must be done in the extension.

Creating and sending the confirm message requires you create the class instance and call the send function. Example (from commands/extension.py):
```py
view = ui.Confirm()
await view.send(
    message=f"Warning! This will replace the current `{extension_name}.py` "
    + "extension! Are you SURE?",
    channel=ctx.channel,
    author=ctx.author,
)
```
Required arguments for send are:
- message: The message to add to the message prompted to the user
- channel: The channel to send the message to
- author: The user who is in control of the confirmation. They are the only ones allowed to interact with it

You MAY add:
- timeout: A custom amount of seconds to wait before defaulting to the timeout response. Default is 60 seconds

If you are calling this from an app command:
- interaction: Is required to properly respond to interactions, the original interaction to reply or follow up with
- ephemeral: If you would like the confirmation message to be sent in an ephemeral form. Optional, defaults to false. This is not available with prefix commands

Additionally, if you are calling this from an app command, you must defer the response (examples below from commands/who.py):
```py
await interaction.response.defer(ephemeral=True)
```
Ephemeral is not required there, but if you pass ephemeral as True to the confirmation window, you must pass it as true to the defer function as well.  
For any additional followups to the message, you must use the view followup variable:
```py
view.followup.send
```

After calling send, you must wait for the view to be completed, by running:
```py
await view.wait()
```

After this line, you can guarantee that you have a `view.value` variable, and it is properly set to what the user picked unless there was a timeout. This value will match the enum values above, you can compare it to:
- ui.ConfirmResponse.CONFIRMED
- ui.ConfirmResponse.DENIED
- ui.ConfirmResponse.TIMEOUT

It is highly recommended that:
- Confirmed - You do the action and inform the user the action was completed
- Denied - You inform the user that the action was cancelled
- Timeout - You silently do nothing

There are times where these recommendations do not make sense, such as in `core/auxiliary.py` in the extension_help function

## Creating guild configuration
For any global guild config, config outside of any particular extension, add a line in the `create_new_context_config` in the core bot.py file.
Add a line such as this:
```py
config_.logging_channel = None
```
To create a new config object, this one is called "logging_channel", and it's under the root config object.
If you wish to make a sub category, do the following:
```py
config_.rate_limit = munch.DefaultMunch(None)
config_.rate_limit.enabled = False
config_.rate_limit.commands = 4
```
This creates, under the root section, a config item under "rate_limit" and then add "enabled" and "commands"


For adding an extension config entry, import the extensionconfig from core:
```py
from core import extensionconfig
```
In the setup function of the extension, create a config object:
```py
config = extensionconfig.ExtensionConfig()
config.add(
    key="manage_roles",
    datatype="list",
    title="Manage factoids roles",
    description="The roles required to manage factoids",
    default=["Factoids"],
)
```
This will create a config item under extensions.MODULE_NAME.key

**Root config, and config for existing extensions will not be created automatically. Upon running a new extensions for the first time, the default config will be added**

## Accessing guild configuration
The guild config is where almost everything should be stored. You need to first get the config for the correct guild. All of the guild configs are stored in a guild_configs list, accessible through the bot object.
```py
config = self.bot.guild_configs[str(guild.id)]
```
You need a guild id in order to get the config.  
Once you have the config, access it using dot notation, like so:
```py
config.extensions.duck.allow_manipulation.value
```
If you attempt to access config that isn't there, you will get a ValueError

## Environment Variables
The environment variables are stored in the .env file. Not all variables are loaded to the discord bot, check the docker-compose.yml file for names and what is passed.

In order to access environment variables, first make sure they are passed to the container in the docker-compose.yml file.  
Second, in the file import os:
```py
import os
```
You can read the environment variables like so:
```py
os.environ.get("DEBUG", 0)
```

These can be read from any file.  
Environment variables should not be used for much, it is only preferred to be used for things that also impact the OS or other container things.

## File config
The file config is stored in config.yml  
You can access the file config anywhere from the bot object, using `bot.file_config`. You do not need to use await/async.  
This object will give you the root, so `bot.file_config.bot_config.auth_token` will get you the bot auth token

## IRC

## Typing
Note: This feature is only avaiable to prefix commands. App commands have interaction.defer, which accomplishes something similar

On the command declaration function, you may add a decorater as such:
```py
@auxiliary.with_typing
```
This will wrap the original function and make the bot say typing until the function has been completed. There will be a brief pause after a message has been sent, but it will return if you are thinking for a followup or waiting for user input (like a confirm).  
While there are other ways to do typing, this is a quick, reliable, and consistent way to add typing and not make the code more complex.

## Permissions checking

## Logging
To use the bots logging system, you will need to import the following:
```py
from botlogging import LogContext, LogLevel
```
The LogLevel is always required, the LogContext is not needed in every log, but will probably be needed

After you have imported, use the following function to log
```py
await self.bot.logger.send_log(
    message=(
        "Could not find factoid referenced by job - will retry after waiting"
    ),
    level=LogLevel.WARNING,
    channel=log_channel,
    context=LogContext(guild=ctx.guild, channel=ctx.channel),
    exception=exception,
)
```
The "message" and "level" arguments are required, the rest are optional.  
The "message" parameter is the text, the logger system will add an embed around this.  
The "level" parameter is using the LogLevel import. You can pick DEBUG, INFO, WARNING, or ERROR.  
The "channel" parameter is what channel to send the log to, provided the guild logging is enabled.  
The "contxt" parameter is the context that the log was generated in. If a command was run in channel X, use that channel in the context. Your context can be only a guild or only a channel if the context demands it.  
The "exception" parameter is an exception object. You can add this regardless of the log level, and an exception will always be printed.

## Event listener

## MatchCog

## LoopCog

## Accessing other cogs
In order to access the class instance of another cog, you can use the get_cog function.
```py
cog = bot.get_cog("HangmanCog")
```
This will get the class instance of the given cog. You can use this to call other functions in a differnet cog, or read data from a different cog

## Getting bot from context or interaction

## Setup function

## Adding new python libraries
If you need to add a new python library to the bot, start by modifying the `Pipfile` file. Add the library you want and the version, ideally the most up to date version.  
Then, run `pipenv lock` in the terminal from the root of the bot. This will update the `Pipfile.lock` file to add depedencies and your new library.  
After that, upon rebuilding the bot container, that library will be installed and able to be used.
