# How to use the bot
After you have got the bot started and connected to discord, this will walk you through how to interact with the bot, get your application command tree updated, modify the guild config, and use extensions.

## First start
When you first start the bot (or when you first join a new guild), you will see a handful of errors. This is due to some extensions not being properly configured from the start. You can configure or disable these. These errors should not cause alarm, they don't mean the bot isn't working right.

## Editing the guild config
The first thing you should do is edit the guild config. Run `.config patch` (or whatever your default prefix is, defined in `config.yml`).  
Download the json file the bot gives you. First, look through the enabled extensions list and disable any extensions you do not want enabled.  
Unless you are ready to modify your config only in the database, you should not disable the config extension.
After you have done that, look through the extension configuration and configure any extensions you need. You can always change this config later.  
Once you have modified the config, upload the json file and run `.config patch` to apply the new config. The config is updated instatly.

## Enabling or disabling extensions
Instead of downloding the entire config file, you are able to run commands to enable or disable extensions.  
`.config enable-extension {name}` and `.config disable-extension {name}`  

## Application command tree
The application command tree isn't automatically updated or created. After you have started the bot, all of the application commands will not be avaiable. Run the `.sync` command update the application command tree.  
You will need to do this every update or when applications commands are changed.  

## Interacting with the bot
After you are all setup, run `.bot` to see the status of the bot. You can see if IRC is connected (if you enabled IRC), what version you have installed, and other tidbits of information.

## Using extensions
After you are done updating the config and picking what extensions you want, you can start using them immediatly.  
Run the commands you want to use, either application or prefix. If you don't know, you can search the help menu by typing `.help {command}` if you have the help extension enabled.
