"""Connect Piccolo to the bot's existing PostgreSQL database."""

import logging

from piccolo.engine.postgres import PostgresEngine

from database import schema
from database.synchronization import synchronize_schema


async def connect(
    *, user: str, password: str, database: str, host: str, port: int
) -> PostgresEngine:
    """Open a pool, bind the tables and synchronize the public database schema.

    Args:
        user (str): The PostgreSQL username
        password (str): The PostgreSQL password
        database (str): The name of the PostgreSQL database
        host (str): The hostname of the PostgreSQL server
        port (int): The port of the PostgreSQL server

    Raises:
        BaseException: Re-raises connection or synchronization failures after pool cleanup

    Returns:
        PostgresEngine: The engine with an open connection pool, bound to the schema's tables
    """
    engine = PostgresEngine(
        config={
            "user": user,
            "password": password,
            "database": database,
            "host": host,
            "port": port,
        }
    )
    await engine.start_connection_pool()
    try:
        schema.bind_engine(engine)
        await synchronize_schema(engine)
    except BaseException:
        await disconnect(engine)
        logging.getLogger(__name__).exception(
            "Database schema initialization failed; changes were rolled back and the pool closed"
        )
        raise
    return engine


async def disconnect(engine: PostgresEngine) -> None:
    """Close the engine's connection pool if it is running.

    Args:
        engine (PostgresEngine): The engine whose connection pool should be closed
    """
    if engine.pool is not None:
        await engine.close_connection_pool()
