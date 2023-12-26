# Dependencies used in this project
This file will talk through what dependencies are used, and what they are used for.

# aiocron
This is used to allow extensions to run things on a cron schedule, to allow for greater customization.  
This is currently used application, factoids, and news

# bidict
This is used to allow a bi-directional lookup for data. This is only used to allow easy and quick lookups from irc channel to discord channel

# black
This is the automatic python code formatter. This is used to format every file in a similar way, and is run in a github action

# dateparser
This is used to allow human readable mute commands. This is only used in protect

# discord.py
This is the core library used for all discord interactions. This is used in nearly every file.

# emoji
Used to turn strings into emoji. Used in the emoji and poll extensions.

# expiringdict
Used to create temporary dicts, this is used in a handful of areas for caching, locks, history, etc.

# gino
Gino is used to interact with postgres in an async day

# gitpython
This is used to interact with the git repo to build the version information in the .bot command

# hypothesis
This is used for property-based testing, used by some unit tests

# ib3
Used to allow IRC to be authenticated with SASL

# inflect
Turns a numeric character into the text for it, used for conversion into emoji in the emoji extension

# irc
Used to interact with irc.

# isort
Used to sort and de-duplicate the imports in every file

# munch
Used to create a dot accessible dicts. Used nearly everywhere

# typing_extensions
This is not used directly in this project, it is only in the Pipfile so the version is locked to avoid surprise failures

# pip
This is used in the Dockerfile to build the bot, and is installed in the github actions.  
This does not need to be in the Pipfile, but is there to avoid a failure due to a bug in pip

# pipenv
This is used to read and install dependencies from Pipfile.lock.  
This does not need to be in the Pipfile, but is there to avoid a failure due to a bug in pipenv

# pydantic
This is not used directly in this project, it is only in the Pipfile so the version is locked to avoid surprise failures

# pynacl
This is not used directly in this project, it is only in the Pipfile so the version is locked to avoid surprise failures

# pytest
The unit test library, this manages all the unit tests, and is used in the github action for unit tests

# pytest-asyncio
This allows for unit tests for async funcitons. This requires the main pytest library

# pyyaml
This is used to read the file config file.

# unidecode
This is used to format usernames properly.
