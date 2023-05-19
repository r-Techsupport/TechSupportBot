[![CodeFactor](https://www.codefactor.io/repository/github/r-techsupport/techsupportbot/badge)](https://www.codefactor.io/repository/github/r-techsupport/techsupportbot)

# TechSupportBot

TechSupportBot is a Dockerized Discord bot. Written on top of the [Python Discord API](https://pycord.readthedocs.io/en/latest/api.html), it provides the loading and unloading of custom extensions to extend and scale the bot as much as you want.

# Deployment Guide
## External setup
You will need to create a discord bot and get the token to be able to use this application. To get your bot created and obtain your token, follow these steps:
1. Go to https://discord.com/developers/applications, sign into your discord account if needed
2. Click on "New Application", name it, then click "Create"
3. On the side menu, go to "Bot" and click "Add bot"
4. Under bot, click "Reset Token", type in 2FA code if prompted, and write down the token. Keep this token secret, you should never share it.
5. Make sure you turn on all the "Privileged Gateway Intents", which are currently "Presence", "Message Content", and "Server Members"
6. To have the bot join your server, go to "OAuth2", "URL Generator". Select "bot" under "Scopes", then select "Administrator". The link to join will be at the bottom of the page.
## Configuration setup
You will need to create and config 2 files to get this system running.  
First, you will need to create the template config files from the default.  
Start by cloning the repo, `git clone git@github.com:r-Techsupport/TechSupportBot.git`.  
Then do the following:  
```bash
cd TechSupportBot
cp default.env .env
cp config.default.yml config.yml
```
### .env file
The first file we will edit is the .env file. This is where you will store database information.  
You will need to create a username and password for mongodb, postgres, and rabbitmq. These credentials do not have to be different.  
You will also need to create a db name for postgres. This works best when it is all lowercase, but it is not strictly required.  
When filling in the information, do not include spaces or quotes. Just put the content directly after the equals sign.  
You will need all of this information again, so make sure to keep note of it.  
### config.yml
This is the configuration file for the bot itself.  
First, configure the token and admin ID. The token is the discord token you got earlier. Put this token in quotes following the `auth_token:` line. Example: `auth_token: "abcd_totally_real_token"`  
For the admin ID, get your user ID by right clicking on your name, either on the side bar or after you sent a message, and clicking "Copy ID". Put your ID in single quotes in the array.  
#### postgres
For postgres, you will need the username, password, and DB name you created previously. Enter it exactly as found in your .env file.  
Do not change the port or host.  
#### mongodb
For mongodb, you will need the username and password you created previously. You will also need to create a DB name here. Enter the username and password exactly as found in your .env file. Just like postgres, the DB name works best with all lowercase, but it is not a requirement.  
Do not change the port or host.  
#### rabbitmq
For rabbitmq, you will only need the username and password you created previously. Enter it exactly as found in your .env file.  
Do not change the host, vhost, or port.  
#### Additional configuration
All the additional configuration is optional, and is not required to start the bot. This includes all API keys. The default settings everywhere else work, but can be changed later if desired.
## Final tasks
The only thing left to do is run `make start`. This will build the container, download the databases, and starts all the containers.

# Makefile

The Makefile offers shortcut commands for development.

* `sync` makes an updated pipenv virtual environment.
* `check-format` checks the formatting without changing files. Required black and isort be installed on your computer.
* `format` checks formatting and changes files. Required black and isort be installed on your computer.
* `lint` runs pylint.
* `test` runs unit tests. (Currently none)
* `build` builds the Docker image.
* `start` starts the entire system, databases and all. This can also be used as a fast update, as it won't force a full rebuild.
* `update` stops all the containers, builds a fresh build of the bot, and starts all containers.
* `clean` removes all unused docker assets, including volumes. This may be destructive.
* `down` brings down the bot container.
* `restart` restarts the bot and all databases.
* `logs` shows the bot logs.
* `establish_config` creates a config.yml file if it doesn't exist.

# Making extensions

On startup, the bot will load all extension files in the `techsupport_bot/extensions/` directory. These files hold commands for the bot to use with its prefix. Each command is an async function decorated as a `command`, and each file must have an entrypoint function called `setup`, which tells the loading process how to add the extension file.

A (very) simple example:
```python
import base
from discord.ext import commands
async def setup(bot):
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
