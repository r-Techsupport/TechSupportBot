# BasementBot

BasementBot is a Dockerized Discord bot. Written on top of the [Python Discord API](https://pycord.readthedocs.io/en/latest/api.html), it provides the loading and unloading of custom extensions to extend and scale the bot as much as you want.

# Setup

Note: *this bot requires at minimum a MongoDB connection to maintain guild settings. If you wish to not use a MongoDB connection, check the base module for bots that don't rely on MongoDB.*

* Create a `config.yaml` file from the `config.default.yaml` file in the repo.
* In the `config.yaml` file set your Discord developer `token` (see [here](https://discordapp.com/developers/docs/topics/oauth2))
* In the `config.yaml` file set MongoDB connection settings (username, password, host, port, etc)
* (Optional) set any other `config.yaml` variables. Some included extensions won't work without the correct API keys.

## Production

* Build the prod image:
    ```
    make prod
    ```

* Run the Docker image using a `docker-compose.yml` configuration (see repo):
    ```
    make upp
    ```

* Check the logs to verify things are working:
    ```
    make logs
    ```

* Run Discord commands with the prefix you set in the `.env` file (defaults to `.`)

## Development

* Build the dev image:
    ```
    make dev
    ```

* Spin up the dev containers:
    ```
    make upd
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
* `upd` spins up the development bot container.
* `upp` spins up the production bot container.
* `down` brings down the bot container.
* `reboot` restarts the dev container.
* `restart` restarts the bot container.
* `logs` shows the main container logs.

# Making extensions

On startup, the bot will load all extension files in the `basement_bot/extensions/` directory. These files hold commands for the bot to use with its prefix. Each command is an async function decorated as a `command`, and each file must have an entrypoint function called `setup`, which tells the loading process how to add the extension file.

A (very) simple example:

```python
import base
from discord.ext import commands


def setup(bot):
    bot.process_extension_setup(cogs=[Greeter])


class Greeter(base.BaseCog):
    @commands.command(
        name="hello",
        brief="Says hello to the bot",
        description="Says hello to the bot (because they are doing such a great job!)",
        usage="",
    )
    async def hello(self, ctx):
        # H, E, Y
        emojis = ["🇭", "🇪", "🇾"]
        for emoji in emojis:
            await ctx.message.add_reaction(emoji)
```

Extensions can be configured per-guild with settings saved on MongoDB. There are several extensions included in the main repo, so please reference them for more advanced examples.
