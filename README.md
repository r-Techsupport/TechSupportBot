# BasementBot

[![Build Status](https://travis-ci.org/effprime/BasementBot.svg?branch=master)](https://travis-ci.org/effprime/BasementBot)

BasementBot is a Discord bot designed for running in Docker. Written on top of the [Python Discord API](https://discordpy.readthedocs.io/en/latest/api.html), it provides loading custom plugins. 

## Setup

* Create a `.env` file:
    ```
    cp default.env .env
    ```

* In the `.env` file set your Discord developer `TOKEN` (see [here](https://discordapp.com/developers/docs/topics/oauth2))

* (Optional) set any other `.env` variables. Some included plugins won't work without the correct API keys.

* Spin up the bot services:
    ```
    docker-compose up -d --build
    ```

* Run commands with the prefix you set in the `.env` file (defaults to `.`):
    ```
    .help
    ```

## Making Plugins

On startup, the bot will load all plugin files in the `basement_bot/plugins/` directory. 

These files hold commands for the bot to use with its prefix. Each command is an async function decorated as a `command`, and each file must have an entrypoint function called `setup`, which tells the loading process how to add the plugin file.

A simple example:

```python
from discord.ext import commands

def setup(bot):
    bot.add_command(my_command)

@commands.command(name="example")
async def my_command(ctx, arg1, arg2, *args):
    await ctx.send("Hello world!")
```

This command would trigger with something like `.example arg arg lots of args`

Each command must have its first arg as `ctx` which is the context for the command event. Each additional arg is an assumption that it be provided by the user (using `*args` helps in this case). 

There are utility functions in `plugin.py` for helping with this process. For example, `tagged_response` sends a message with the command author tagged.

For more information, see [the Discord.py docs](https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html).