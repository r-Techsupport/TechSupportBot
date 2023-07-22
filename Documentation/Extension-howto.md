All extensions should be placed into the extensions folder.
Note: Docstrings will be excluded in this guide but should always be included when actually coding.

This file will show you how to create extensions, what every part of them does.

# Setup

```py
async def setup(bot):
```
This code is run when loading the extension, is used to add model classes and config entries.


## Models

This defines any database models used in this extension.

```py
class Model_name(bot.db.Model):
    __tablename__ = "<table-name>"

    Int_Entry = bot.db.Column(bot.db.Integer, primary_key=True)
    Str_Entry = bot.db.Column(bot.db.String, default=None)
    guild = bot.db.Column(bot.db.String)
```
This creates a table called `<table-name>` and adds the columns `Int_entry`, `Str_entry`and `guild` to it. 
Make sure to include `guild` along with handling for it so the entry is only callable in the server a command was invoked from.
The `default` argument is optional but preferred, since an exception will be thrown if there wasn't a value assigned but it is attempted to be accessed.


## Config entries

```py
config = bot.ExtensionConfig()
config.add(
    key="<key>",
    datatype="<datatype",
    title="<title>",
    description="<description>",
    default="<default-value>",
)
```
This defines the config, then defines its values.
The config.json returned by `.config patch` will have the following value added to it:
```json
"<extension-name>": {
    "<key>": {
        "datatype": "<datatype>",
        "title": "<title>",
        "description": "<description>",
        "default": "<default>",
        "value": "<default>"
        }
}
```
NOTE: The entry might not automatically get added to the file and will have to be added in manually according to the template above.


## Registering the extension

```py
await bot.add_cog(extension-name(bot=bot))
bot.add_extension_config("extension-name", config)
```
This registers the extension, assumes the extension name is the filename if the `extension_name` argument wasn't supplied. If any custom models are defined, make sure to add the `models` argument with its value being `[Model_name_1, Model_name_2, ...]`

The second line adds the extension to the config .json file.


## Optional: Command checks

This defines checks used for commands, it should return a bool value.
For example a check whether the command invokation message contain any mentions:
```py
async def no_mentions(ctx):
    if (
        ctx.message.mention_everyone
        or ctx.message.role_mentions
        or ctx.message.mentions
        or ctx.message.channel_mentions
    ):
        await auxiliary.send_deny_embed(
            message="I cannot remember factoids with user/role/channel mentions",
            channel=ctx.channel
        )
        return False
    return True

```
(Example taken from the factoids extension)


## DEPRACATED: Embed class

Some extensions have a class for its specific embed, this has been replaced because of its complexity and repetitiveness.
It's included for the sake of completency, but new code should always use the `generate_basic_embed` from auxiliary.py instead of this class.

```py
class AbcEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()
```
This creates a class for the embed accesible from the main extension class, its values will be defined by the arguments it is called with. 
In this example the color will automatically be set to green.

Example:
```py
embed = AbcEmbed(title="Hello world", description="Sample text")
```



# The main command class

```py
class Extension_name(base.MatchCog):
```

This is where we define all command groups and their respective commands, along with preconfig and other functions used later in the code.
When making command code, please make the actual decorated functions just refer to a separate, asynchronously defined function earlier in the file to:
1) Improve readability
2) Improve maintainability
3) Decrease code repetition


## Making embeds

To make embeds, use the `generate_basic_embed` method from auxiliary.py.
The arguments to supply:
- `title` - The title of the embed
- `description` - The description of the embed
- `color` - The color of the embed
- `url` - The thumbnail picture URL


## Optional: Preconfig

```py
async def preconfig(self):
    self.nice_value_bro = {}
    await self.start_doing_your_thing()
```
The rough equivalent of `__init__` - It is run one time before the extension is ever ran.
Defines attributes, starts any tasks. 


## Defining command groups

This will hold the first command called, for example `.factoid`. If our new extension only has one command, feel free to skip this.
Even though it executes no code, we add an automatic help trigger that is called when there are no arguments (subcommands) supplied.

```py
 @commands.group(
        brief="Short-description",
        description="Long-description",
    )
    async def command-group-name():

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])
```
This defines a command group that is called using `.command-group-name <command>`.
The help is included and called if it is called by itself, should be included unless the command group itself serves a purpose.

Note: The help call uses `self.module[11:]` since that is the most reliable way to get the actual extension name, since it always contains `extensions:<extension-name>`


## Command definition

Now that we have everything set up, we can define an actual command.

```py
@util.with_typing
@commands.check(check-name)
@commands.guild_only()
@commands.cooldown(1, 60, commands.BucketType.channel)
@commands.command(
    name="<command_name>",
    aliases=["<alias-1", "alias-2"],
    brief="<short-description>",
    description="<long-description>",
    usage="[string-arg] [int-arg]",
)
async def <command-name>(self, ctx, arg1: str, arg2: int):
```
This defines the actual command.
- `@util.with_typing` - Makes the bot say `<bot> is typing...` while this command is being executed
- `@commands.check(check-name)` - This runs a command check defined earlier
- `@commands.guild_only()` - This makes sure the command can only be run within a guild
- `@commands.cooldown(<count>, <time>, commands.BiucketType.channel)` - This defines a cooldown for the command, it can be called <count> times per <time>
- `@commands.command` - This defines the command itself and has the following arguments:
* `name` - The command name
* `aliases` - A list of alternate ways to call the command
* `brief` - Short description of the command
* `description` - Long usage of the command
* `usage` - Displayed in the help command as such: `.commmand-name command <usage>`
NOTE: The etiquette used for `usage`is the following: `[]` indicates text input, `||` indicates file input.

Please make sure to use type hints for the arguments of the command method.



# Command contents

Now that the command method is defined, you can start writing its code.


## Querying the DB

The bot uses the `gino` module to query database entries.

The following query checks for any entires of Model_name where Value-1 is "Sample text", the guild is the same as the one where the command was invoked.

```py
(await self.models.<Model_name>.query.where(self.models.<Model_name>.Value-1 == "Sample text")
.where(self.models.<Model_name>.guild == str(guild.id))
.gino.all())
```
Make sure to include the `guild` line so only entries that were added from the server a command was invoked from are returned.

You can also use `gino.first()` to get the first value instead of a list of the entries.


## Adding a DB entry

To add an entry to the DB, add it using the `self.models.<Model_name>.create()` followed by awaiting the `.create()` method.

An example:
```py
sample = self.models.<Model_name>(
    Value_1="",
    Value_2="",
    Value_3="",
)
await sample.create()
```


## Removing a DB entry

To remove an entry from the DB, get the entry using `.gino.first()` and await it with the `.delete()` method.

An example:
```py
sample = (
    await self.models.<Model_name>.query.where(self.models.<Model_name>.Value-1 == "Sample text")
    .where(self.models.<Model_name>.guild == str(guild.id))
    .gino.first()
    )
await sample.delete()
```

## Accessing the config

The bot uses two types of config:
- config.yml - Used primarily for API keys
- json config - Accessed via `.config patch`, holdso ther misc values

To add values to config.yml, you have to manually append them to it and default.config.yml respectively.
To access the values, you can use the following:
```py
self.bot.file_config.main.cfg-group-name.value-name
```
---
To access the json config, you can add the following line of code, which loads the guild config file:
```py
config = await self.bot.get_context_config(guild=ctx.guild)
```

Afterwards you can access the values with 
```py
config.extensions.<Ext-name>.<Value-name>.value
```

## Calling an API

All API calls use the `http_call` method defined in data.py
The arguments to supply:
- `method` - The http call method (PUT/POST etc.)
- `url` - The endpoint URL to send the request to
- `data` (kwarg) - Data to send to the API
- `headers` (kwarg) - Headers to send to the api
    
The response is returned as a dictionary.
    
An example from dumpdbg.py:
```py
response = await self.bot.http_call(
    "post",
    api_endpoint,
    data=json_data,
    headers={"Content-Type": "application/json"},
)
```


## Returning a message

To return a message, use `await ctx` with any of the following methods:

- `send(embed=<embed>)` - This sends a custom embed that has to be defined manually

You can also use `await auxiliary` with any of the following methods:

- `send_deny_embed("<message>")` - This sends a red embed with a custom message
- `send_confirm_embed("<message>")` - This sends a green embed with a custom message