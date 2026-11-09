"""Connect Piccolo to the bot's existing PostgreSQL database."""

from piccolo.engine.postgres import PostgresEngine

from database.schema import Grab


async def connect(
    *, user: str, password: str, database: str, host: str, port: int
) -> PostgresEngine:
    """Open a pool and bind Grab without changing the database schema."""
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
    Grab._meta.db = engine
    return engine


async def disconnect(engine: PostgresEngine) -> None:
    """Close an active connection pool."""
    if engine.pool is not None:
        await engine.close_connection_pool()
