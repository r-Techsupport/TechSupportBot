from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, configuration

if TYPE_CHECKING:
    import bot


async def has_manage_factoids_role(
    interaction: discord.Interaction,
) -> bool:
    """A command check to determine if the invoker has a configured manage role

    Args:
        interaction (discord.Interaction): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    return await has_given_factoids_role(
        interaction.guild,
        interaction.user,
        configuration.get_config_entry(interaction.guild.id, "factoids_manage_roles"),
    )


async def has_admin_factoids_role(interaction: discord.Interaction) -> bool:
    """A command check to determine if the invoker has a configured admin role

    Args:
       interaction (discord.Interaction): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    return await has_given_factoids_role(
        interaction.guild,
        interaction.user,
        configuration.get_config_entry(interaction.guild.id, "factoids_admin_roles"),
    )


async def has_given_factoids_role(
    guild: discord.Guild, invoker: discord.Member, check_roles: list[str]
) -> bool:
    """-COMMAND CHECK-
    Checks if the invoker has a factoid management role

    Args:
        guild (discord.Guild): The guild the factoids command was called in
        invoker (discord.Member): This is the member who called the factoids command
        check_roles (list[str]): The list of string names of roles

    Raises:
        CommandError: No management roles assigned in the config
        MissingAnyRole: Invoker doesn't have a factoid management role

    Returns:
        bool: Whether the invoker has a factoid management role
    """
    factoid_roles = []
    # Gets permitted roles
    for name in check_roles:
        factoid_role = discord.utils.get(guild.roles, name=name)
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise app_commands.AppCommandError(
            "No factoid management roles found in the config file"
        )
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        factoid_role in getattr(invoker, "roles", []) for factoid_role in factoid_roles
    ):
        raise app_commands.MissingAnyRole(factoid_roles)

    return True


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Factoid plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(FactoidManager(bot=bot))


class FactoidManager(cogs.BaseCog):

    FACTOID_FLAG_DISABLED = 0b1000
    FACTOID_FLAG_HIDDEN = 0b0100
    FACTOID_FLAG_PROTECTED = 0b0010
    FACTOID_FLAG_RESTRICTED = 0b0001

    factoid_app_group: app_commands.Group = app_commands.Group(
        name="factoid", description="Command Group for the Factoids Extension"
    )

    # DATABASE
    # TODO: Add caching

    async def create_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
        factoid_data_id: int,
    ) -> bot.models.FactoidCall:
        """This creates a new factoid call database entry for the given guild and factoid

        Args:
            self (Self): _description_
            guild (discord.Guild): The guild to create the factoid in
            name (str): The name of the factoid call to create
            factoid_data_id (int): The factoid data entry to associate this call with

        Returns:
            bot.models.FactoidCall: The newly created database entry
        """

        return await self.bot.models.FactoidCall.create(
            guild=str(guild.id),
            name=name,
            factoid_data_id=factoid_data_id,
        )

    async def read_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> bot.models.FactoidCall:
        """Searches the database for a factoid call for the passed guild

        Args:
            guild (discord.Guild): The guild to find the factoid call of
            name (str): The name of the factoid to search for

        Returns:
            bot.models.FactoidCall: The database entry for the factoid call
        """

        return await self.bot.models.FactoidCall.query.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == name)
        ).gino.first()

    async def delete_factoid_data(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> None:
        """Deletes factoid data from the database
        This does not impact factoid jobs or factoid calls

        Args:
            guild (discord.Guild): The guild the factoid data is stored in
            factoid_data_id (int): The ID of the data entry to delete
        """

        await self.bot.models.FactoidData.delete.where(
            (self.bot.models.FactoidData.guild == str(guild.id))
            & (self.bot.models.FactoidData.factoid_data_id == factoid_data_id)
        ).gino.status()

    async def create_factoid_data(
        self: Self,
        guild: discord.Guild,
        message: str,
        json_string: str,
        flags: int,
    ) -> bot.models.FactoidData:
        """Creates a new factoid data entry in the table
        This will not create a call to this factoid

        Args:
            guild (discord.Guild): The guild to create this factoid for
            message (str): The plaintext version of the factoid
            json_string (str): The json for this factoid
            flags (int): The property binary flags for this factoid

        Returns:
            bot.models.FactoidData: The newly created database entry
        """

        return await self.bot.models.FactoidData.create(
            guild=str(guild.id),
            message=message,
            json_string=json_string,
            flags=flags,
            times_called=0,
        )

    async def read_factoid_data(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> bot.models.FactoidData:
        """Searches the database for a factoid data for the passed guild

        Args:
            guild (discord.Guild): The guild to find the factoid call of
            factoid_data_id (int): The ID of the factoid to search for

        Returns:
            bot.models.FactoidData: The database entry for the factoid call
        """

        return await self.bot.models.FactoidData.query.where(
            (self.bot.models.FactoidData.guild == str(guild.id))
            & (self.bot.models.FactoidData.factoid_data_id == factoid_data_id)
        ).gino.first()

    async def delete_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> None:
        """Deletes a factoid call by name."""

        await self.bot.models.FactoidCall.delete.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == name)
        ).gino.status()

    async def get_factoid_calls_by_factoid_id(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> list:
        """Returns all calls pointing to a factoid."""

        return await self.bot.models.FactoidCall.query.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.factoid_data_id == factoid_data_id)
        ).gino.all()

    # DATABASE HELPERS

    async def get_factoid_data_by_name(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> bot.models.FactoidData:
        """Searches for the factoid data associated with a given factoid name

        Args:
            guild (discord.Guild): The guild to look for the factoid in
            name (str): The name of the factoid to lookup

        Returns:
            bot.models.FactoidData: The database entry of the factoid data, if found
        """

        call = await self.read_factoid_call(
            guild=guild,
            name=name,
        )

        if call is None:
            return None

        return await self.read_factoid_data(
            guild=guild,
            factoid_data_id=call.factoid_data_id,
        )

    async def delete_factoid_by_name(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> bool:
        """
        Deletes a factoid call.
        If it was the last call, deletes the underlying factoid data too.
        Returns True if anything was deleted.
        """

        call = await self.get_factoid_call(
            guild=guild,
            name=name,
        )

        if call is None:
            return False

        factoid_data_id = call.factoid_data_id

        # delete the call first
        await self.delete_factoid_call(
            guild=guild,
            name=name,
        )

        # check remaining calls
        remaining_calls = await self.get_factoid_calls_by_factoid_id(
            guild=guild,
            factoid_data_id=factoid_data_id,
        )

        if not remaining_calls:
            await self.delete_factoid_data(
                guild=guild,
                factoid_data_id=factoid_data_id,
            )

        return True

    async def move_factoid_call(
        self: Self,
        guild: discord.Guild,
        existing_name: str,
        new_factoid_data_id: int,
    ) -> bool:
        """
        Moves a factoid call to a different factoid data entry.

        If the old factoid_data loses all calls, it is deleted.
        Returns True if the move succeeded.
        """

        call = await self.read_factoid_call(
            guild=guild,
            name=existing_name,
        )

        if call is None:
            return False

        old_factoid_data_id = call.factoid_data_id

        # Update the call to point to the new factoid
        await self.bot.models.FactoidCall.update.values(
            factoid_data_id=new_factoid_data_id
        ).where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == existing_name)
        ).gino.status()

        # Check if the old factoid is now orphaned
        remaining_calls = await self.get_factoid_calls_by_factoid_id(
            guild=guild,
            factoid_data_id=old_factoid_data_id,
        )

        # If there aren't any calls, prevent having orphaned factoids in the database at all
        if not remaining_calls:
            await self.delete_factoid_data(
                guild=guild,
                factoid_data_id=old_factoid_data_id,
            )

        return True

    # OTHER HELPERS

    def can_channel_send_restricted(
        self: Self, channel: discord.abc.GuildChannel
    ) -> bool:
        """This checks if the given channel is in the restricted channel list.
        Can handle parsing threads

        Args:
            self (Self): _description_
            channel (discord.abc.GuildChannel): The channel trying to see the factoid

        Returns:
            bool: Whether the restricted factoid can be sent
        """
        if isinstance(channel, discord.Thread):
            channel = channel.parent

        restricted_channel_list = configuration.get_config_entry(
            channel.guild.id, "factoids_restricted_list"
        )

        if str(channel.id) in restricted_channel_list:
            return True
        return False

    def get_embed_from_factoid(
        self: Self, factoid: bot.models.FactoidData
    ) -> discord.Embed:
        """Gets the factoid embed from its database entry

        Args:
            factoid (bot.models.FactoidData): The factoid to get the json of

        Returns:
            discord.Embed: The embed of the factoid
        """
        if not factoid.json_string:
            return None

        embed_config = json.loads(factoid.json_string)

        return discord.Embed.from_dict(embed_config)

    async def confirm_factoid_deletion(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        channel: discord.abc.GuildChannel,
        author: discord.Member,
    ) -> ui.ConfirmResponse:
        """Confirms if a factoid should be deleted/modified

        Args:
            factoid_name (str): The factoid that is being prompted for deletion
            channel (discord.abc.GuildChannel): The channel the factoid is being deleted in
            author (discord.Member): The member deleting the factoid
            fmt (str): Formatting for the returned message

        Returns:
            bool: Whether the factoid was deleted/modified
        """
        view = ui.Confirm()
        await view.send(
            message=(
                f"The factoid `{factoid_name}` already exists. Should I overwrite it?"
            ),
            channel=channel,
            author=author,
            interaction=interaction,
        )

        await view.wait()
        return view.value

    # AUTOFILL

    async def factoid_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Suggests factoids for autofill for commands that need autofilled factoids

        Args:
            interaction (discord.Interaction): The interaction calling the factoids
            current (str): The current string value of the factoid argument

        Returns:
            list[app_commands.Choice[str]]: The list of suggestions
        """

        guild = interaction.guild
        if guild is None:
            return []

        current = current.lower()

        factoids = (
            await self.bot.models.FactoidCall.query.where(
                (self.bot.models.FactoidCall.guild == str(guild.id))
                & (self.bot.models.FactoidCall.name.ilike(f"{current}%"))
            )
            .order_by(self.bot.models.FactoidCall.name)
            .limit(25)
            .gino.all()
        )

        return [
            app_commands.Choice(
                name=factoid.name,
                value=factoid.name,
            )
            for factoid in factoids
        ]

    # COMMANDS

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="add",
        description="Creates a new factoid by name",
    )
    async def factoid_add_command(
        self: Self, interaction: discord.Interaction, factoid_name: str
    ) -> None:
        factoid_name = factoid_name.lower()

        # Only ever attempt to add a factoid if it doesn't exist
        if await self.read_factoid_call(guild=interaction.guild, name=factoid_name):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` already exists"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        form = NewFactoid(factoid_name)
        await interaction.response.send_modal(form)
        await form.wait()

        embed_json_string = ""

        if form.embed.component.values:
            embed_file: discord.Attachment = form.embed.component.values[0]

            if not embed_file.filename.endswith(".json"):
                embed = auxiliary.prepare_deny_embed(
                    message="I don't recognize your upload as a JSON file.",
                )
                await interaction.followup.send(embed=embed)
                return

            try:
                json_bytes = await embed_file.read()
                attachment_json = json.loads(json_bytes.decode("UTF-8"))
                embed_json_string = json.dumps(attachment_json)

            except Exception:
                embed = auxiliary.prepare_deny_embed(
                    message="I couldn't parse the uploaded JSON file.",
                )
                await interaction.followup.send(embed=embed)
                return

        selected = set(form.properties.component.values)

        property_binary = (
            ("disabled" in selected) << 3
            | ("hidden" in selected) << 2
            | ("protected" in selected) << 1
            | ("restricted" in selected)
        )

        factoid = await self.create_factoid_data(
            guild=interaction.guild,
            message=form.plaintext.component.value,
            json_string=embed_json_string,
            flags=property_binary,
        )

        await self.create_factoid_call(
            guild=interaction.guild,
            name=factoid_name,
            factoid_data_id=factoid.factoid_data_id,
        )

        embed = auxiliary.prepare_confirm_embed(
            message=f"Your factoid `{factoid_name}` was successfully created!",
        )
        await interaction.followup.send(embed=embed)

        # Send the factoid, and embed json if exists, to the user
        await interaction.followup.send(content=factoid.message, ephemeral=True)
        if embed_json_string:
            try:
                embed = self.get_embed_from_factoid(factoid=factoid)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(
                    f"The embed you upload failed: {exc}", ephemeral=True
                )

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="alias",
        description="Creates an alias for an existing factoid call",
    )
    @app_commands.autocomplete(existing_factoid=factoid_autocomplete)
    async def factoid_alias_command(
        self: Self,
        interaction: discord.Interaction,
        existing_factoid: str,
        new_factoid: str,
    ) -> None:
        existing_factoid = existing_factoid.lower()
        new_factoid = new_factoid.lower()

        factoid = await self.get_factoid_data_by_name(
            guild=interaction.guild, name=existing_factoid
        )

        # We can't alias a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{existing_factoid}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No aliases on protected factoids
        if factoid.flags & self.FACTOID_FLAG_DISABLED:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{existing_factoid}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        new_factoid_db = await self.get_factoid_data_by_name(
            guild=interaction.guild, name=new_factoid
        )

        # If the existing and new calls already point to the same factoid, there is nothing to do
        if new_factoid_db and factoid.factoid_data_id == new_factoid_db.factoid_data_id:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{new_factoid}` is already an alias of `{existing_factoid}`."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # If the new_factoid already exists but point elsewhere, we need to ask the user for confirmation
        if new_factoid_db:
            await interaction.response.defer()
            confirmation_response = await self.confirm_factoid_deletion(
                interaction=interaction,
                factoid_name=new_factoid,
                channel=interaction.channel,
                author=interaction.user,
            )
            if confirmation_response == ui.ConfirmResponse.TIMEOUT:
                return
            elif confirmation_response == ui.ConfirmResponse.DENIED:
                embed = await auxiliary.prepare_deny_embed(
                    message=f"The factoid `{new_factoid}` was not replaced.",
                )
                interaction.followup.send(embed=embed)
                return
            else:
                await self.move_factoid_call(
                    guild=interaction.guild,
                    existing_name=new_factoid,
                    new_factoid_data_id=factoid.factoid_data_id,
                )
        else:
            await self.create_factoid_call(
                guild=interaction.guild,
                name=new_factoid,
                factoid_data_id=factoid.factoid_data_id,
            )

        embed = auxiliary.prepare_deny_embed(
            message=f"Successfully added the alias `{new_factoid}` for `{existing_factoid}`",
        )
        # Depending on the path took to get here, we may need to followup
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="call",
        description="Calls a factoid from the database and sends it publicy in the channel.",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
    async def factoid_call_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        member_to_ping: discord.Member = None,
    ) -> None:
        """This is an app command version of typing {prefix}call
        This is the preferred method of getting factoids

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid name to search for and print
            member_to_ping (discord.Member): A member to ping in the output

        Raises:
            TooLongFactoidMessageError: If the plaintext exceed 2000 characters
        """
        # TODO: Generic this to support prefix commands?
        factoid_name = factoid_name.lower()
        factoid = await self.get_factoid_data_by_name(
            guild=interaction.guild, name=factoid_name
        )
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` couldn't be found"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if factoid is disabled. If so, don't send it
        if factoid.flags & self.FACTOID_FLAG_DISABLED:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is disabled."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if factoid is restricted. If so, check if we can call it
        if (
            factoid.flags & self.FACTOID_FLAG_RESTRICTED
            and not self.can_channel_send_restricted(interaction.channel)
        ):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is restricted and not allowed in this channel."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        plaintext_content = factoid.message
        embed = None

        if not configuration.get_config_entry(
            interaction.guild.id, "factoids_disable_embeds"
        ):
            try:
                embed = self.get_embed_from_factoid(factoid)
            except TypeError as exception:
                await self.bot.logger.send_log(
                    message=(
                        f"Unable to make embed for factoid `{factoid_name}`, "
                        "sending fallback."
                    ),
                    level=LogLevel.ERROR,
                    channel=configuration.get_config_entry(
                        interaction.guild.id,
                        "core_logging_channel",
                    ),
                    context=LogContext(
                        guild=interaction.guild,
                        channel=interaction.channel,
                    ),
                    exception=exception,
                )

        content = ""
        if member_to_ping:
            content = member_to_ping.mention

        embed_sent = False
        if embed:
            try:
                # This view allows the caller to delete the factoid
                view = DeleteView(interaction.user.id)

                # Attempt to send the message with the embed in it
                await interaction.response.send_message(
                    content=content,
                    embed=embed,
                    view=view,
                )

                view.message = await interaction.original_response()
                # log it in the logging channel with type info and generic content
                log_channel = configuration.get_config_entry(
                    interaction.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=(
                        f"Sending factoid: `{factoid_name}` (triggered by {interaction.user} in"
                        f" #{interaction.channel.name})"
                    ),
                    level=LogLevel.INFO,
                    context=LogContext(
                        guild=interaction.guild, channel=interaction.channel
                    ),
                    channel=log_channel,
                )
                embed_sent = True
            # If something breaks, also log it
            except discord.errors.HTTPException as exception:
                log_channel = configuration.get_config_entry(
                    interaction.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message="Could not send factoid",
                    level=LogLevel.ERROR,
                    context=LogContext(
                        guild=interaction.guild, channel=interaction.channel
                    ),
                    channel=log_channel,
                    exception=exception,
                )

        # Either no embed exists, or the embed failed to send for some reason.
        # We will send the plaintext content of the factoid in this case
        if not embed_sent:
            content += f" {plaintext_content}"
            content = content.strip()
            if len(content) > 2000:
                embed = auxiliary.prepare_deny_embed(
                    message=f"The factoid `{factoid_name}` is too long and cannot be sent on discord."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            view = DeleteView(interaction.user.id)
            await interaction.response.send_message(content=content, view=view)
            view.message = await interaction.original_response()

        # TODO: Send to IRC
        # TODO: Send to Logger


class DeleteView(discord.ui.View):
    """The class to hold the view for the delete button on /factoid call

    Args:
        author_id (int): The ID of the author of the factoid
    """

    def __init__(self: Self, author_id: int) -> None:
        super().__init__(timeout=300)
        self.author_id = author_id
        self.message: discord.Message | None = None

    async def on_timeout(self: Self) -> None:
        """Is called after the timeout, with the goal of deleting the buttons from the message"""

        if self.message:
            await self.message.edit(view=None)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the delete button is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the original caller can delete this message.",
                ephemeral=True,
            )
            return

        if interaction.message:
            await interaction.message.delete()


class NewFactoid(discord.ui.Modal):
    """A Modal that contains information to make a new factoid
    This has the user fill in plaintext content, upload an embed json file
    And select default properties for the factoid

    Args:
        factoid (str): The name of the factoid, to display in the title

    Attributes:
        plaintext (discord.ui.Label): The plaintext representation of the factoid
        embed (discord.ui.Label): The json file attachment of the factoid
        properties (discord.ui.Label): The properties of the factoid, such as hidden or disabled
    """

    def __init__(self: Self, factoid: str) -> None:
        super().__init__(title=f"Creating factoid {factoid}")

    plaintext: discord.ui.Label = discord.ui.Label(
        text="Plaintext:",
        component=discord.ui.TextInput(style=discord.TextStyle.long, required=True),
    )
    embed: discord.ui.Label = discord.ui.Label(
        text="Embed json:", component=discord.ui.FileUpload(required=False)
    )
    properties: discord.ui.Label = discord.ui.Label(
        text="Properties:",
        component=discord.ui.CheckboxGroup(
            max_values=4,
            required=False,
            options=[
                discord.CheckboxGroupOption(
                    default=False, label="Disabled", value="disabled"
                ),
                discord.CheckboxGroupOption(
                    default=False, label="Hidden", value="hidden"
                ),
                discord.CheckboxGroupOption(
                    default=False, label="Protected", value="protected"
                ),
                discord.CheckboxGroupOption(
                    default=False, label="Restricted", value="restricted"
                ),
            ],
        ),
    )

    async def on_submit(self: Self, interaction: discord.Interaction) -> None:
        """What happens when the form has been successfully submitted

        Args:
            interaction (discord.Interaction): The interaction that caused the form to be show
        """
        await interaction.response.defer()
        return
