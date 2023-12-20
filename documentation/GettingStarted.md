In this file you will find some useful information about the project, the layout of the project, and how to get started developing.

# What is this project?
This is a discord bot, written in python using the discord.py library, mainly designed for the r/TechSupport discord server. However, it is supposed to be general purpose, so it can be used in other situations as well.  

# Layout
The code for this is all under the techsupport_bot folder. Inside you will see a collection of folders:
- botlogging - This folder is for the logging system. This is how discord logs get sent and queued, how console logs are decided, and many other logging features.
- commands - This is where files containing all of the commands the bot uses are held.
- core - This is core functions to the bot that are required for most commands to work, but not required for the bot to start
- functions - This is where files containing extensions to the bot exist, but these extensions do not have a command associated with them
- ircrelay - This is where the core of the IRC bot and all helper files are located
- resources - Non code files that are refereced as sources of information to keep code files more direct
- tests - Currently a very small set of unit tests, run by pytest, that are designed to run on every push
- ui - This is generic discord UI elements, such as confirmation or pagination. These are designed to be used and provide only basic functionality

The majority of the work in this project will be done in the commands folder.

# Terminology
Cogs or extensions can be used to refer to the collection of both commands and functions. The files in these folders function almost identically, with the only difference being to keep things organized.

# Formatting
To keep the project consistent, all changes must follow some basic formatting rules:
- Black and isort are used to auto format the code in a consistent way.
- All files must use LF line endings. Any file using CR or CRLF endings will not be accepted.
- Pylint is run to validate that things like docstrings are used everywhere to help document the code.

# Setting up a development environment (linux)
> For information about how to get the bot started, please see README.md  
You do not need anything special, everything can be done with the bare minimum of getting the bot started. However, having a local install of python and packages will help.
> Going forward, it is assumed you have an install of python, pip, and pipenv
The fastest way to setup the development environment is to use pipenv. You can create a development environment by navigating to the repo folder and running `pipenv install`. This will install all of the project dependencies and correct versions for you. Going forward, to enter this environment just run `pipenv shell` from the repo folder.  
This setup will allow you to run tools like black or pytest directly from your terminal instead of having to use the docker container or waiting for github actions.
