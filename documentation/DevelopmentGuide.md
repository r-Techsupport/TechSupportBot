# The (command/function) development guide
The purpose of this document is to highlight how common things you will need to interact with during modification or creation of extensions of the bot.  
This is mainly focused on extensions, but parts of this can be reused in core development as well

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

## Reading data from postgres
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
        self.bot.models.Applications.application_stauts
        == ApplicationStatus.PENDING.value
    )
)
entry = await query.gino.first()
```

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

## Creating slash commands

## Creating context menu entires

## Creating prefix commands

## Context vs interaction

## Responding to the user

## Creating custom embeds

## Pagination

## Confirmation

## Creating guild configuration

## Accessing guild configuration

## Environment Variables

## File config

## IRC

## Typing

## Permissions checking

## Logging

## Event listener

## MatchCog

## LoopCog

## Accessing other cogs

## Getting bot from context or interaction

## Setup function
