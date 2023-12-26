All extensions should be placed into the extensions folder.
Note: Docstrings will be excluded in this guide but should always be included when actually coding.

This file will show you how to create extensions, what every part of them does.

# Setup

```py
async def setup(bot):
```
This code is run when loading the extension, is used to add model classes and config entries.

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


# The main command class

```py
class Extension_name(cogs.MatchCog):
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
        await auxiliary.extension_help(self, ctx, self.__module__[9:])
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

## Returning a message

To return a message, use `await ctx` with any of the following methods:

- `send(embed=<embed>)` - This sends a custom embed that has to be defined manually

You can also use `await auxiliary` with any of the following methods:

- `send_deny_embed("<message>")` - This sends a red embed with a custom message
- `send_confirm_embed("<message>")` - This sends a green embed with a custom message