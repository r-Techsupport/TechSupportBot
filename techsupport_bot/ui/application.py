import traceback

import discord


class Application(discord.ui.Modal, title="Staff interest form"):
    # Our modal classes MUST subclass `discord.ui.Modal`,
    # but the title can be whatever you want.

    # This will be a short input, where the user can enter their name
    # It will also have a placeholder, as denoted by the `placeholder` kwarg.
    # By default, it is required and is a short-style input which is exactly
    # what we want.
    background = discord.ui.TextInput(
        label="Do you have any IT or programming experience?",
        placeholder="I made facebook and I...",
        style=discord.TextStyle.long,
        required=True,
        max_length=300,
    )

    # This is a longer, paragraph style input, where user can submit feedback
    # Unlike the name, it is not required. If filled out, however, it will
    # only accept a maximum of 300 characters, as denoted by the
    # `max_length=300` kwarg.
    reason = discord.ui.TextInput(
        label="Why do you want to help here?",
        placeholder="I am really good at fixing light bulbs...",
        style=discord.TextStyle.long,
        required=True,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Your application has been recieved, {interaction.user.display_name}!",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong. Try again or tell the server moderators if"
            " this keeps happening.",
            ephemeral=True,
        )

        # Make sure we know what the error actually is
        traceback.print_exception(type(error), error, error.__traceback__)
