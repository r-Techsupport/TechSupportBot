

    @staticmethod
    async def is_reader(interaction: discord.Interaction) -> bool:
        """Checks whether invoker can read notes. If at least one reader
        role is not set, NO members can read notes

        Args:
            interaction (discord.Interaction): The interaction in which the whois command occured

        Raises:
            MissingAnyRole: Raised if the user is lacking any reader role,
                but there are roles defined
            AppCommandError: Raised if there are no note_readers set in the config

        Returns:
            bool: True if the user can run, False if they cannot
        """

        config = interaction.client.guild_configs[str(interaction.guild.id)]
        if reader_roles := config.extensions.who.note_readers.value:
            roles = (
                discord.utils.get(interaction.guild.roles, name=role)
                for role in reader_roles
            )
            status = any((role in interaction.user.roles for role in roles))
            if not status:
                raise app_commands.MissingAnyRole(reader_roles)
            return True

        # Reader_roles are empty (not set)
        message = "There aren't any `note_readers` roles set in the config!"
        embed = auxiliary.prepare_deny_embed(message=message)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        raise app_commands.AppCommandError(message)

    @app_commands.check(is_reader)
    @app_commands.command(
        name="whois",
        description="Gets Discord user information",
        extras={"brief": "Gets user data", "usage": "@user", "module": "who"},
    )
    async def get_note(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """This is the base of the /whois command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to lookup. Will not work on discord.User
        """
        embed = discord.Embed(
            title=f"User info for `{user}`",
            description="**Note: this is a bot account!**" if user.bot else "",
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Created at", value=user.created_at.replace(microsecond=0))
        embed.add_field(name="Joined at", value=user.joined_at.replace(microsecond=0))
        embed.add_field(
            name="Status", value=interaction.guild.get_member(user.id).status
        )
        embed.add_field(name="Nickname", value=user.display_name)

        role_string = ", ".join(role.name for role in user.roles[1:])
        embed.add_field(name="Roles", value=role_string or "No roles")

        # Adds special information only visible to mods
        if interaction.permissions.kick_members:
            embed = await self.modify_embed_for_mods(interaction, user, embed)

        user_notes = await self.get_notes(user, interaction.guild)
        total_notes = 0
        if user_notes:
            total_notes = len(user_notes)
            user_notes = user_notes[:3]
        embed.set_footer(text=f"{total_notes} total notes")
        embed.color = discord.Color.dark_blue()

        for note in user_notes:
            author = interaction.guild.get_member(int(note.author_id)) or note.author_id
            embed.add_field(
                name=f"Note from {author} ({note.updated.date()})",
                value=f"*{note.body}*" or "*None*",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def modify_embed_for_mods(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        embed: discord.Embed,
    ) -> discord.Embed:
        """Makes modifications to the whois embed to add mod only information

        Args:
            interaction (discord.Interaction): The interaction where the /whois command was called
            user (discord.Member): The user being looked up
            embed (discord.Embed): The embed already filled with whois information

        Returns:
            discord.Embed: The embed with mod only information added
        """
        # If the user has warnings, add them
        warnings = (
            await self.bot.models.Warning.query.where(
                self.bot.models.Warning.user_id == str(user.id)
            )
            .where(self.bot.models.Warning.guild_id == str(interaction.guild.id))
            .gino.all()
        )
        warning_str = ""
        for warning in warnings[-3:]:
            warning_moderator_name = "unknown"
            if warning.invoker_id:
                warning_moderator = await self.bot.fetch_user(int(warning.invoker_id))
                if warning_moderator:
                    warning_moderator_name = warning_moderator.name

            warning_str += (
                f"- {warning.reason} - <t:{int(warning.time.timestamp())}:R>. "
            )
            warning_str += f"Warned by: {warning_moderator_name}\n"

        if warning_str:
            embed.add_field(
                name=f"**Warnings ({len(warnings)} total)**",
                value=warning_str,
                inline=True,
            )

        # If the user has a pending application, show it
        # If the user is banned from making applications, show it
        application_cog = interaction.client.get_cog("ApplicationManager")
        if application_cog:
            has_application = await application_cog.search_for_pending_application(user)
            is_banned = await application_cog.get_ban_entry(user)
            embed.add_field(
                name="Application information:",
                value=(
                    f"Has pending application: {bool(has_application)}\nIs banned from"
                    f" making applications: {bool(is_banned)}"
                ),
                inline=True,
            )
        return embed
