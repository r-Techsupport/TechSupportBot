# Documentation for functions in the auxiliary file
The auxiliary.py file contains a bunch of standalone functions used by the core and extensions alike. These functions exist mainly for consistency and easy of updating.  
Another major reason for this file is unit testing. The majority of the functions in this file have extensive unit tests made for them. This allows for a selection of core functions to be almost guaranteed bug free, so when creating or modifying extensions you know you know the auxiliary funtions are not the cause of bugs

## generate_basic_embed
This function exists to be a baseline embed generation tool. This is to replace every extension having their own basic embed generation function that is slightly differnet. This will allow more consistency and easier updates.

This function only sets 4 parameters and returns a basic formatted embed. It requires a title, description, and color. You may pass it an icon url as well.

## search_channel_for_message
This function will search the last 50 messages in a channel for a message matching parameters given, such as author, content, or bot commands. This will return the most recent message that matches the search parameters. If no messages exists matching these parameters, None will be returned.

This function exists to replace the similar function in many extensions. While it has to be a little more complex to allow a choice of what is being searched for, it allows much more consistency is the search itself and allows for easier modifications to all uses

## add_list_of_reactions
This function adds a list of reactions to a given messages one at a time. While not very complicated, this is used in a handful of commands, and centralizing it makes sense to ensure consistency and functionality.

## construct_mention_string

## prepare_deny_embed

## send_deny_embed

## prepare_confirm_embed

## send_confirm_embed

## get_json_from_attachments

## config_schema_matches
This function checks to ensure that the new guild config and old guild config contain the same keys. If they don't contain the same keys, an array of added or removed keys is returned.

## with_typing
This function is intended to be used as a decorator to allow the bot to show typing while a command is processing.

## get_object_diff

## add_diff_fields

## get_help_embed_for_extension

## extension_help
