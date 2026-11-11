"""Bot-admin commands for exporting and replacing individual tables as CSV."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Self

import asyncpg
import discord
from discord import app_commands
from piccolo.conf.apps import table_finder
from piccolo.table import Table

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


def _identifier(name: str) -> str:
    """Quote a PostgreSQL identifier.

    Args:
        name (str): The physical column, table or schema name

    Returns:
        str: The escaped identifier
    """
    return '"' + name.replace('"', '""') + '"'


def _tables() -> dict[str, type[Table]]:
    """Discover the tables declared in the current Piccolo schema.

    Returns:
        dict[str, type[Table]]: The models keyed by physical table name
    """
    return {
        model._meta.tablename: model  # pylint: disable=protected-access
        for model in table_finder(["database.schema"], exclude_imported=True)
    }


def _table(name: str) -> tuple[str, str]:
    """Resolve a declared table to its quoted SQL name and primary-key column.

    Args:
        name (str): The physical table name selected by the admin

    Raises:
        ValueError: Raised when the table is not declared in the Piccolo schema

    Returns:
        tuple[str, str]: The qualified table name and unquoted primary-key name
    """
    model = _tables().get(name)
    if model is None:
        raise ValueError("Select a table from the database schema")
    schema_name = model._meta.schema or "public"  # pylint: disable=protected-access
    key = model._meta.primary_key  # pylint: disable=protected-access
    primary_key = key._meta.db_column_name  # pylint: disable=protected-access
    return f"{_identifier(schema_name)}.{_identifier(name)}", primary_key


async def _export_csv(
    connection: asyncpg.Connection, table: str, size_limit: int
) -> io.BytesIO:
    """Export a table using PostgreSQL CSV encoding within Discord's size limit.

    Args:
        connection (asyncpg.Connection): The database connection
        table (str): The qualified and quoted table name
        size_limit (int): The maximum attachment size in bytes

    Raises:
        ValueError: Raised if the export is larger than Discord permits

    Returns:
        io.BytesIO: The CSV file, positioned at the beginning
    """
    output = io.BytesIO()
    too_large = False

    async def write_chunk(chunk: bytes) -> None:
        """Buffer a COPY chunk without exceeding the attachment limit.

        Args:
            chunk (bytes): The next CSV chunk from PostgreSQL

        """
        nonlocal too_large
        too_large = too_large or output.tell() + len(chunk) > size_limit
        if not too_large:
            output.write(chunk)

    await connection.copy_from_query(
        f"SELECT * FROM {table}",
        output=write_chunk,
        format="csv",
        header=True,
        encoding="UTF8",
    )
    if too_large:
        output.close()
        raise ValueError("This table's CSV exceeds Discord's attachment size limit")
    output.seek(0)
    return output


async def _import_csv(
    connection: asyncpg.Connection, table: str, primary_key: str, content: bytes
) -> int:
    """Replace table rows atomically, preserving references to matching IDs.

    Args:
        connection (asyncpg.Connection): The database connection
        table (str): The qualified and quoted table name
        primary_key (str): The physical primary-key column name
        content (bytes): The UTF-8 CSV file, optionally beginning with a BOM

    Raises:
        ValueError: Raised when CSV headers do not match the table's columns

    Returns:
        int: The number of rows in the imported table
    """
    text = content.decode("utf-8-sig")
    headers = next(csv.reader(io.StringIO(text, newline=""), strict=True), [])
    async with connection.transaction():
        await connection.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        statement = await connection.prepare(f"SELECT * FROM {table} LIMIT 0")
        columns = [attribute.name for attribute in statement.get_attributes()]
        if len(headers) != len(set(headers)) or set(headers) != set(columns):
            raise ValueError(
                "CSV headers must contain every table column exactly once: "
                + ", ".join(columns)
            )

        staging = 'pg_temp."database_import"'
        await connection.execute(
            f"CREATE TEMP TABLE {staging} (LIKE {table}) ON COMMIT DROP"
        )
        key = _identifier(primary_key)
        await connection.execute(f"ALTER TABLE {staging} ADD PRIMARY KEY ({key})")
        await connection.copy_to_table(
            "database_import",
            schema_name="pg_temp",
            source=io.BytesIO(text.encode("utf-8")),
            columns=headers,
            format="csv",
            header=True,
            encoding="UTF8",
        )
        column_list = ", ".join(_identifier(column) for column in columns)
        updates = ", ".join(
            f"{_identifier(column)} = EXCLUDED.{_identifier(column)}"
            for column in columns
            if column != primary_key
        )
        conflict = f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
        await connection.execute(
            f"INSERT INTO {table} ({column_list}) "
            f"SELECT {column_list} FROM {staging} WHERE true "
            f"ON CONFLICT ({key}) {conflict}"
        )
        await connection.execute(
            f"DELETE FROM {table} AS target WHERE NOT EXISTS "
            f"(SELECT 1 FROM {staging} AS source WHERE source.{key} = target.{key})"
        )
        # ALTER SEQUENCE RESTART is transactional, unlike setval.
        sequence = await connection.fetchval(
            "SELECT pg_get_serial_sequence($1,$2)", table, primary_key
        )
        if sequence is not None:
            settings = await connection.fetchrow(
                "SELECT seqstart,seqincrement FROM pg_sequence WHERE seqrelid=$1::regclass",
                sequence,
            )
            aggregate = "max" if settings["seqincrement"] > 0 else "min"
            extreme = await connection.fetchval(
                f"SELECT {aggregate}({key}) FROM {table}"
            )
            next_id = (
                settings["seqstart"]
                if extreme is None
                else extreme + settings["seqincrement"]
            )
            next_id = (
                max(next_id, settings["seqstart"])
                if settings["seqincrement"] > 0
                else min(next_id, settings["seqstart"])
            )
            await connection.execute(
                f"ALTER SEQUENCE {sequence} RESTART WITH {next_id}"
            )
        return await connection.fetchval(f"SELECT count(*) FROM {staging}")


async def setup(bot: bot.TechSupportBot) -> None:
    """Register the database administration commands.

    Args:
        bot (bot.TechSupportBot): The bot receiving the cog
    """
    await bot.add_cog(DatabaseCommands(bot=bot))


class DatabaseCommands(cogs.BaseCog):
    """Export and replace the contents of declared Piccolo tables.

    Attributes:
        database_group (app_commands.Group): The group for the /database commands
    """

    database_group: app_commands.Group = app_commands.Group(
        name="database",
        description="Import and export database tables",
        guild_only=True,
    )

    async def table_autocomplete(
        self: Self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest current schema table names only to bot admins.

        Args:
            interaction (discord.Interaction): The autocomplete interaction
            current (str): The partial table name entered by the admin

        Returns:
            list[app_commands.Choice[str]]: Up to 25 matching physical table names
        """
        if not await interaction.client.is_bot_admin(interaction.user):
            return []
        return [
            app_commands.Choice(name=name, value=name)
            for name in sorted(_tables())
            if current.casefold() in name.casefold()
        ][:25]

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @database_group.command(
        name="export",
        description="Export a table's rows as CSV",
        extras={"ephemeral_error": True},
    )
    @app_commands.autocomplete(table=table_autocomplete)
    async def export_table(
        self: Self, interaction: discord.Interaction, table: str
    ) -> None:
        """Export the selected table to an ephemeral CSV attachment.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            table (str): The physical table name to export
        """
        await interaction.response.defer(ephemeral=True)
        try:
            qualified, _ = _table(table)
            async with self.bot.db.pool.acquire() as connection:
                content = await _export_csv(
                    connection, qualified, interaction.filesize_limit
                )
            attachment = discord.File(content, filename=f"{table}.csv")
            try:
                await interaction.followup.send(file=attachment, ephemeral=True)
            finally:
                attachment.close()
                content.close()
        except (
            asyncpg.PostgresError,
            ValueError,
        ) as error:
            embed = auxiliary.prepare_deny_embed(message=str(error)[:1500])
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @database_group.command(
        name="import",
        description="Replace a table's rows with an uploaded CSV",
        extras={"ephemeral_error": True},
    )
    @app_commands.autocomplete(table=table_autocomplete)
    async def import_table(
        self: Self,
        interaction: discord.Interaction,
        table: str,
        csv_file: discord.Attachment,
    ) -> None:
        """Replace table contents transactionally from an ephemeral CSV upload.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            table (str): The physical table name whose rows will be replaced
            csv_file (discord.Attachment): The UTF-8 CSV file to import

        Raises:
            ValueError: Raised when the uploaded filename is not a CSV file
        """
        await interaction.response.defer(ephemeral=True)
        try:
            qualified, primary_key = _table(table)
            if not csv_file.filename.lower().endswith(".csv"):
                raise ValueError("Upload a CSV file")
            content = await csv_file.read()
            async with self.bot.db.pool.acquire() as connection:
                count = await _import_csv(connection, qualified, primary_key, content)
            embed = auxiliary.prepare_confirm_embed(
                message=f"Imported {count} rows into {table}; its previous contents were replaced"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except (
            asyncpg.PostgresError,
            ValueError,
            csv.Error,
        ) as error:
            embed = auxiliary.prepare_deny_embed(message=str(error)[:1500])
            await interaction.followup.send(embed=embed, ephemeral=True)
