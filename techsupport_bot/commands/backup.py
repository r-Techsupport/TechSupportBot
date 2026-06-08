"""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

import csv
import zipfile
from typing import TYPE_CHECKING, Self

import discord
import yaml
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the slowmode cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(BackupCommand(bot=bot))


class BackupCommand(cogs.BaseCog):
    """The cog that holds the slowmode commands and helper functions"""

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @app_commands.command(
        name="backup",
        description="Backs up data into a zip file",
        extras={
            "module": "backup",
        },
    )
    async def backup(
        self: Self, interaction: discord.Interaction, config_file: bool = False
    ) -> None:
        """Gets a data backup of everything

        Args:
            interaction (discord.Interaction): The interaction that called this command
            config_file (bool): Sets whether to include the yaml config file in the zip or not
        """
        # Databases
        csv_files = []
        for table_name, table in self.bot.models.items():
            # Query all data from the table
            data = await table.query.gino.all()

            # Save data to a CSV file
            csv_file = f"{table_name}.csv"
            with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
                if data:
                    fieldnames = (
                        data[0].to_dict().keys()
                    )  # Convert the first row to a dict to get the field names
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in data:
                        writer.writerow(row.to_dict())
            csv_files.append(csv_file)

        # Config file
        if config_file:
            yaml_file = "loaded_config.yaml"
            with open(yaml_file, "w", encoding="utf8") as outfile:
                yaml.dump(
                    self.bot.file_config,
                    outfile,
                    default_flow_style=False,
                    allow_unicode=True,
                )

        # Guilds
        guilds_file = "guilds.txt"
        with open(guilds_file, "w", encoding="utf-8") as file:
            for guild in self.bot.guilds:
                file.write(f"{guild.name} (ID: {guild.id})\n")

        temp_zip = "temp_data.zip"
        with zipfile.ZipFile(temp_zip, "w") as zipf:
            for csv_file in csv_files:
                zipf.write(csv_file)
            if config_file:
                zipf.write(yaml_file)
            zipf.write(guilds_file)

        # Upload the ZIP file in a message
        with open(temp_zip, "rb") as fp:
            await interaction.response.send_message(
                file=discord.File(fp, "data_backup.zip"), ephemeral=True
            )
