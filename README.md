# BasementBot

[![Build Status](https://travis-ci.org/effprime/BasementBot.svg?branch=master)](https://travis-ci.org/effprime/BasementBot)

BasementBot is a Discord bot designed for running in Docker. Written on top of the [Python Discord API](https://discordpy.readthedocs.io/en/latest/api.html), it provides the loading and unloading of custom plugins.

# Setup

* Create a `.env` file from the `default.env` file in the repo.
* In the `.env` file set your Discord developer `TOKEN` (see [here](https://discordapp.com/developers/docs/topics/oauth2))
* (Optional) set any other `.env` variables. Some included plugins won't work without the correct API keys.

## Production

* Fill out the settings appropriate to your bot.

* Pull the latest Docker image:
    ```
    docker pull effprime/basement-bot:latest
    ```

* Run the Docker image using a `docker-compose.yml` configuration (see repo):
    ```
    docker-compose up -d
    ```

* Check the logs to verify things are working:
    ```
    docker logs basement_bot
    ```

* Run commands with the prefix you set in the `.env` file (defaults to `.`):
    ```
    .help
    ```

## Development

* Build the dev image:
    ```
    make dev
    ```

* Spin up the dev containers:
    ```
    make upd
    ```

* Build the prod image:
    ```
    make prod
    ```

# Makefile

The Makefile offers shortcut commands for development.

* `sync` makes an updated pipenv virtual environment.
* `check-format` checks the formatting without changing files.
* `format` checks formatting and changes files.
* `lint` runs pylint.
* `test` runs unit tests.
* `dev` builds the dev Docker image.
* `prod` builds the prod Docker image.
* `upd` spins up the development bot containers.
* `upp` spins up the production bot containers.
* `down` brings down the bot containers.
* `restart` restarts the bot containers.
* `logs` shows the main container logs.

# Making Plugins

On startup, the bot will load all plugin files in the `basement_bot/plugins/` directory. 

These files hold commands for the bot to use with its prefix. Each command is an async function decorated as a `command`, and each file must have an entrypoint function called `setup`, which tells the loading process how to add the plugin file.

A (very) simple example:

```python
from discord.ext import commands

def setup(bot):
    bot.add_command(my_command)

@commands.command(name="example")
async def my_command(ctx, word, other_word, *args):
    await ctx.send("Hello world!")
```

This command would trigger with something like `.example hello greetings ha ha ha`

Each command must have its first arg as `ctx` which is the context for the command event. Each additional arg is an assumption that it be provided by the user (using `*args` helps in this case). 

There are utility functions in `utils.helpers` or `cogs` modules for helping with this plugin-building process. For example, `utils.helpers.tagged_response` sends a message with the command author tagged. All plugins included with the repo are written as cog classes for a more structured approach. You can find information on this in the Discord.py docs.

More advanced plugins can be written by interfacing with the bot's API. For instance, the admin plugin allows you to load and unpload plugins. You can also give the bot async tasks to run forever, or event listeners for a specific message.

For more information, see [the Discord.py docs](https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html).
