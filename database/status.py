"""Read-only connection health and schema adherence reporting."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

import asyncpg
from piccolo.conf.apps import table_finder
from piccolo.engine.postgres import PostgresEngine

from database.synchronization import (
    LOCK_ID,
    differences,
    expected_schema,
    inspect_schema,
)


@dataclass(frozen=True)
class ConnectionStatus:
    """The result of a live database connection check.

    Attributes:
        connected (bool): Whether the pool could acquire a connection and execute a query
        error (str | None): The reason the check failed, if any
        checked_at (datetime): The timezone-aware UTC time the check completed
    """

    connected: bool
    error: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SchemaStatus:
    """The result of comparing the live database with the declared Piccolo schema.

    Attributes:
        matches (bool | None): Whether the schema matches, or None if it could not be checked
        differences (list[str]): The detected differences, empty when matching or unavailable
        error (str | None): The reason the check could not complete, if any
        checked_at (datetime): The timezone-aware UTC time the check completed
    """

    matches: bool | None
    differences: list[str] = field(default_factory=list)
    error: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def get_connection_status(
    engine: PostgresEngine | None, *, timeout: float = 5.0
) -> ConnectionStatus:
    """Probe the existing pool without opening or reconnecting it.

    Args:
        engine (PostgresEngine | None): The bot's database engine, or None before initialization
        timeout (float): The maximum seconds to acquire a connection and execute the probe

    Returns:
        ConnectionStatus: The live connection health or the reason it is unavailable
    """
    if engine is None or engine.pool is None:
        return ConnectionStatus(connected=False, error="Database pool is not running")
    try:
        async with asyncio.timeout(timeout):
            async with engine.pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
        return ConnectionStatus(connected=True)
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        OSError,
    ) as error:
        return ConnectionStatus(
            connected=False, error=str(error) or type(error).__name__
        )


async def get_schema_status(
    engine: PostgresEngine | None, *, timeout: float = 5.0
) -> SchemaStatus:
    """Report live schema adherence without applying changes or logging drift.

    Args:
        engine (PostgresEngine | None): The bot's database engine, or None before initialization
        timeout (float): The maximum seconds for acquisition, locking and schema inspection

    Returns:
        SchemaStatus: The current differences, or an unknown status if inspection fails
    """
    if engine is None or engine.pool is None:
        return SchemaStatus(matches=None, error="Database pool is not running")
    try:
        async with asyncio.timeout(timeout):
            async with engine.pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    # Wait for startup migrations, then prevent another from racing inspection.
                    await connection.execute(
                        "SELECT pg_advisory_xact_lock_shared($1)", LOCK_ID
                    )
                    await connection.execute(
                        "SET LOCAL search_path TO public, pg_catalog"
                    )
                    models = table_finder(["database.schema"], exclude_imported=True)
                    drift = differences(
                        expected_schema(models), await inspect_schema(connection)
                    )
        return SchemaStatus(matches=not drift, differences=drift)
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        OSError,
        ValueError,
    ) as error:
        return SchemaStatus(matches=None, error=str(error) or type(error).__name__)
