[![CodeFactor](https://www.codefactor.io/repository/github/r-techsupport/techsupportbot/badge)](https://www.codefactor.io/repository/github/r-techsupport/techsupportbot)

# BasementBot

BasementBot is a Dockerized Discord bot. Written on top of the [Python Discord API](https://pycord.readthedocs.io/en/latest/api.html), it provides the loading and unloading of custom extensions to extend and scale the bot as much as you want.

# Setup

Note: *this bot requires at minimum a MongoDB connection to maintain guild settings. If you wish to not use a MongoDB connection, check the base module for bots that don't rely on MongoDB.* **Some extensions also rely on postgres (factoids and more) and rabbitmq.**

* Create a `config.yml` file from the `config.default.yml` file in the repo.
* In the `config.yml` file set `auth_token` to your Discord developer `token` (see [here](https://discordapp.com/developers/docs/topics/oauth2))
* In the `config.yml` file set MongoDB connection settings (username, password, host, port, etc)
* (Optional) set any other `config.yml` variables. Some included extensions won't work without the correct API keys.

## MongoDB deployment
### Deploying directly onto the host
Note: MongoDB 5.0 x86_64 and later require a CPU that supports the AVX instruction set, it's recommended to use version 4.4.
See [here](https://www.mongodb.com/docs/manual/administration/install-on-linux/) for an installation guide.

It's assumed that the bot is being deployed into a Docker container, as such extra configuration is necessary.
Edit the `mongod` config located at `/etc/mongod.conf` to allow the Docker container's IP address:
```
# network interfaces
net:
  port: 27017
  bindIp: 127.0.0.1,172.17.0.1
```

Edit `docker-compose.yml` to include the below under `bot`:
```
        extra_hosts:
            - "host.docker.internal:host-gateway"
```

Update the `config.yml` file as such:
```
    mongodb:
        user: user
        password: password
        name: dbname
        host: "host.docker.internal"
        port: 27017
```
The `user`, `password`, and `name` fields should be updated as you see fit. It does not matter what you choose, but this info will be relevant when setting up `mongodb`.

From inside the `mongodb` shell:
```
use admin
```
Switch to the `admin` db, allowing us to create a database admin user for the bot.

```
db.createUser({	user: "user", pwd: "password", roles:[{role: "userAdminAnyDatabase" , db:"admin"}]})
```
Create an admin user for the bot to connect as, remember to set `user`
 and `password` to the values you specified in `config.yml`.

```
exit
```
Close the `mongodb` shell. 


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
