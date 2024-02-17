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
        self.bot.models.Applications.application_status
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

## Accessing guild configuration

## Environment Variables

## File config

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

## Event listener

## MatchCog

## LoopCog

## Accessing other cogs

## Getting bot from context or interaction

## Setup function

## Adding new python libraries
