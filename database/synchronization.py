"""Compare and synchronize the public PostgreSQL schema at startup.

Piccolo stores table and column definitions in its public-facing ``_meta``
objects; reading those objects is necessary to discover the declared schema.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import IntEnum

import asyncpg
from piccolo.conf.apps import table_finder
from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table, sort_table_classes

# Piccolo exposes schema definitions through _meta, with no public alternative.
# pylint: disable=protected-access

logger = logging.getLogger(__name__)
LOCK_ID = 648204330761


class SchemaMode(IntEnum):
    """The permitted startup schema operations.

    Attributes:
        REPORT (int): Report differences without changing the database
        ADD (int): Create missing tables and columns only
        HARD (int): Reconcile all managed schema definitions
    """

    REPORT: int = 0
    ADD: int = 1
    HARD: int = 2


def configured_mode() -> SchemaMode:
    """Read the schema mode, defaulting to add-only for missing or invalid values.

    Returns:
        SchemaMode: The mode selected by DATABASE_SCHEMA_MODE
    """
    value = os.environ.get("DATABASE_SCHEMA_MODE", "").strip()
    if not value:
        return SchemaMode.ADD
    try:
        return SchemaMode(int(value))
    except ValueError:
        logger.warning("Invalid DATABASE_SCHEMA_MODE=%r; using 1 (add only)", value)
        return SchemaMode.ADD


def quote(name: str) -> str:
    """Quote a PostgreSQL identifier.

    Args:
        name (str): The unquoted identifier

    Returns:
        str: The escaped identifier
    """
    return '"' + name.replace('"', '""') + '"'


def qualified(name: str) -> str:
    """Qualify a table or sequence in the managed public schema.

    Args:
        name (str): The object name

    Returns:
        str: The qualified, quoted name
    """
    return f'"public".{quote(name)}'


def canonical(sql: str | None) -> str:
    """Normalize equivalent PostgreSQL definitions without changing string literals.

    Args:
        sql (str | None): An SQL expression or definition

    Returns:
        str: The normalized expression
    """
    if sql is None:
        return "null"
    parts = re.split(r"('(?:[^']|'')*')", sql.strip())
    for index in range(0, len(parts), 2):
        text = parts[index].lower()
        text = re.sub(r'"([a-z_][a-z_0-9]*)"', r"\1", text)
        text = text.replace("public.", "")
        text = re.sub(
            r"::(?:character varying|varchar|text|boolean|integer|bigint|double precision|numeric)\b",
            "",
            text,
        )
        text = re.sub(r"\bnow\(\)", "current_timestamp", text)
        text = re.sub(r" on (?:update|delete) no action", "", text)
        parts[index] = text
    result = "".join(parts)
    # PostgreSQL deparses Boolean and numeric defaults as quoted, typed literals.
    if re.fullmatch(r"'(?:true|false|-?\d+(?:\.\d+)?)'", result):
        result = result[1:-1]
    if result == "current_timestamp()":
        result = "current_timestamp"
    # Tokenize outside strings so whitespace inside a default string remains significant.
    return " ".join(
        re.findall(
            r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|[a-z_][a-z_0-9]*|-?\d+(?:\.\d+)?|[^\s]",
            result,
        )
    )


def column_type(value: str) -> str:
    """Normalize PostgreSQL type aliases, including serial's storage type.

    Args:
        value (str): The type spelling from Piccolo or PostgreSQL

    Returns:
        str: The canonical SQL type
    """
    value = value.lower().strip()
    aliases = {
        "serial": "integer",
        "bigserial": "bigint",
        "smallserial": "smallint",
        "int4": "integer",
        "int8": "bigint",
        "int2": "smallint",
        "bool": "boolean",
        "float8": "double precision",
        "float4": "real",
        "timestamptz": "timestamp with time zone",
        "timestamp": "timestamp without time zone",
    }
    value = aliases.get(value, value)
    value = re.sub(r"^varchar\b", "character varying", value)
    return re.sub(r"\s+", " ", value)


@dataclass(frozen=True)
class ColumnSpec:
    """Comparable column properties.

    Attributes:
        sql_type (str): The normalized PostgreSQL type
        nullable (bool): Whether null values are allowed
        default (str): The canonical default expression
        serial (bool): Whether the column has an owned serial sequence
        generated (str): Identity or generated-column metadata
        sequence (tuple): The serial sequence settings, excluding its current value
    """

    sql_type: str
    nullable: bool
    default: str
    serial: bool = False
    generated: str = ""
    sequence: tuple = ()


@dataclass
class TableSpec:
    """An expected or actual table definition.

    Attributes:
        columns (dict[str, ColumnSpec]): The column definitions
        constraints (dict[str, str]): Constraint names and canonical definitions
        indexes (dict[str, tuple]): Index names and comparable definitions
        references (set[str]): Public tables referenced by foreign keys
        definitions (dict[str, str]): Column DDL used for alterations and creation
        defaults (dict[str, str]): SQL defaults used when altering columns
        constraint_sql (dict[str, str]): SQL definitions used to restore constraints
        index_sql (dict[str, str]): SQL statements used to restore indexes
        model (type[Table] | None): The corresponding Piccolo model, if declared
    """

    columns: dict[str, ColumnSpec] = field(default_factory=dict)
    constraints: dict[str, str] = field(default_factory=dict)
    indexes: dict[str, tuple] = field(default_factory=dict)
    references: set[str] = field(default_factory=set)
    definitions: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, str] = field(default_factory=dict)
    constraint_sql: dict[str, str] = field(default_factory=dict)
    index_sql: dict[str, str] = field(default_factory=dict)
    model: type[Table] | None = None


@dataclass
class SchemaSyncResult:
    """The outcome of one startup schema comparison.

    Attributes:
        mode (SchemaMode): The selected operation mode
        differences (list[str]): Differences found before applying changes
        remaining (list[str]): Differences remaining after synchronization
    """

    mode: SchemaMode
    differences: list[str]
    remaining: list[str]


def _serial_settings(type_name: str) -> tuple:
    """Return PostgreSQL's default settings for an owned serial sequence.

    Args:
        type_name (str): The normalized integer storage type

    Returns:
        tuple: The type, start, increment, bounds, cache size and cycling flag
    """
    maximum = {"smallint": 32767, "integer": 2147483647, "bigint": 9223372036854775807}[
        type_name
    ]
    return (type_name, 1, 1, 1, maximum, 1, False)


def expected_schema(models: list[type[Table]]) -> dict[str, TableSpec]:
    """Build expected definitions from the current Piccolo models.

    Args:
        models (list[type[Table]]): The tables declared by this checkout

    Raises:
        ValueError: Raised for model features outside the supported public schema

    Returns:
        dict[str, TableSpec]: The expected tables keyed by physical table name
    """
    expected = {}
    for model in models:
        if model._meta.schema not in (None, "public"):
            raise ValueError("Startup synchronization only supports public tables")
        name = model._meta.tablename
        spec = TableSpec(model=model)
        expected[name] = spec
        for column in model._meta.columns:
            col = column._meta.db_column_name
            raw_type = column.column_type
            serial = raw_type.upper() in ("SERIAL", "BIGSERIAL", "SMALLSERIAL")
            if column.generated is not None:
                raise ValueError(
                    "Declare serial columns instead of identity/generated columns for schema synchronization"
                )
            type_name = column_type(raw_type)
            default = "" if serial else column.get_sql_value(column.get_default_value())
            spec.columns[col] = ColumnSpec(
                type_name,
                column._meta.null and not column._meta.primary_key,
                "serial" if serial else canonical(default),
                serial,
                sequence=_serial_settings(type_name) if serial else (),
            )
            spec.defaults[col] = default
            definition = f"{quote(col)} {raw_type}"
            if not spec.columns[col].nullable:
                definition += " NOT NULL"
            if not serial:
                definition += f" DEFAULT {default}"
            spec.definitions[col] = definition
            if column._meta.primary_key:
                spec.constraint_sql[f"{name}_pkey"] = f"PRIMARY KEY ({quote(col)})"
            if column._meta.unique:
                spec.constraint_sql[f"{name}_{col}_key"] = f"UNIQUE ({quote(col)})"
            foreign = getattr(column, "_foreign_key_meta", None)
            if foreign:
                target = foreign.resolved_references._meta.tablename
                target_col = foreign.resolved_target_column._meta.db_column_name
                if foreign.resolved_references._meta.schema not in (None, "public"):
                    raise ValueError(
                        "Cross-schema model foreign keys are not supported"
                    )
                spec.references.add(target)
                spec.constraint_sql[f"{name}_{col}_fkey"] = (
                    f"FOREIGN KEY ({quote(col)}) REFERENCES {qualified(target)} ({quote(target_col)}) ON UPDATE {foreign.on_update.value} ON DELETE {foreign.on_delete.value}"
                )
            if column._meta.index:
                index_name = f"{name}_{col}"
                method = column._meta.index_method.value
                spec.indexes[index_name] = (
                    method,
                    (canonical(quote(col)),),
                    False,
                    "",
                    True,
                    True,
                )
                spec.index_sql[index_name] = (
                    f"CREATE INDEX {quote(index_name)} ON {qualified(name)} USING {method} ({quote(col)})"
                )
        for constraint in model._meta.constraints:
            spec.constraint_sql[constraint._meta._name] = constraint.ddl
        spec.constraints = {
            key: canonical(value) for key, value in spec.constraint_sql.items()
        }
    return expected


async def inspect_schema(connection: asyncpg.Connection) -> dict[str, TableSpec]:
    """Read ordinary public tables and their definitions without executing DDL.

    Args:
        connection (asyncpg.Connection): The connection used for catalog inspection

    Returns:
        dict[str, TableSpec]: The live database definitions
    """
    names = await connection.fetch(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname"
    )
    actual = {row["relname"]: TableSpec() for row in names}
    columns = await connection.fetch("""
        SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod) AS type,
               a.attnotnull, a.attidentity::text AS attidentity, a.attgenerated::text AS attgenerated,
               pg_get_expr(d.adbin,d.adrelid) AS default,
               pg_get_serial_sequence(format('%I.%I',n.nspname,c.relname),a.attname) AS sequence
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum
    """)
    for row in columns:
        sequence = ()
        serial = bool(
            row["sequence"]
            and not row["attidentity"]
            and (row["default"] or "").startswith("nextval(")
        )
        if serial:
            sequence_default = re.fullmatch(
                r"nextval\('((?:[^']|'')*)'::regclass\)", row["default"]
            )
            serial = bool(sequence_default) and await connection.fetchval(
                "SELECT to_regclass($1) = to_regclass($2)",
                sequence_default.group(1).replace("''", "'"),
                row["sequence"],
            )
        if serial:
            sequence_row = await connection.fetchrow(
                "SELECT format_type(seqtypid,NULL),seqstart,seqincrement,seqmin,seqmax,seqcache,seqcycle FROM pg_sequence WHERE seqrelid=$1::regclass",
                row["sequence"],
            )
            sequence = tuple(sequence_row)
        actual[row["relname"]].columns[row["attname"]] = ColumnSpec(
            column_type(row["type"]),
            not row["attnotnull"],
            "serial" if serial else canonical(row["default"]),
            serial,
            row["attidentity"] + row["attgenerated"],
            sequence,
        )
    constraints = await connection.fetch("""
        SELECT c.relname, k.conname, pg_get_constraintdef(k.oid,true) AS definition,
               r.relname AS referenced, rn.nspname AS referenced_schema
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_class r ON r.oid=k.confrelid
        LEFT JOIN pg_namespace rn ON rn.oid=r.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
    """)
    for row in constraints:
        spec = actual[row["relname"]]
        spec.constraints[row["conname"]] = canonical(row["definition"])
        if row["referenced_schema"] == "public":
            spec.references.add(row["referenced"])
    indexes = await connection.fetch("""
        SELECT c.relname, x.relname AS name, am.amname, i.indisunique, i.indisvalid,
               NOT i.indnullsnotdistinct AS nulls_distinct,
               COALESCE(pg_get_expr(i.indpred,i.indrelid),'') AS predicate,
               ARRAY(SELECT pg_get_indexdef(i.indexrelid,k,true)
                     FROM generate_series(1,i.indnatts) k) AS columns,
               i.indnkeyatts, i.indnatts
        FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
        JOIN pg_class x ON x.oid=i.indexrelid JOIN pg_am am ON am.oid=x.relam
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
          AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid=i.indexrelid)
    """)
    for row in indexes:
        # Included columns are distinct from key columns, even if their names match.
        columns_key = tuple(canonical(value) for value in row["columns"])
        if row["indnkeyatts"] != row["indnatts"]:
            columns_key += (f"include:{row['indnkeyatts']}",)
        actual[row["relname"]].indexes[row["name"]] = (
            row["amname"],
            columns_key,
            row["indisunique"],
            canonical(row["predicate"]),
            row["indisvalid"],
            row["nulls_distinct"],
        )
    return actual


def _constraint_matches(expected: TableSpec, actual: TableSpec) -> bool:
    """Compare constraints while ignoring automatically assigned constraint names.

    Args:
        expected (TableSpec): The declared table constraints
        actual (TableSpec): The catalog constraints

    Returns:
        bool: Whether definitions and explicitly declared names match
    """
    remaining = dict(actual.constraints)
    for name, definition in expected.constraints.items():
        # Piccolo's explicitly declared constraints retain their configured names.
        if name in {c._meta._name for c in expected.model._meta.constraints}:
            if remaining.pop(name, None) != definition:
                return False
        else:
            match = next(
                (key for key, value in remaining.items() if value == definition), None
            )
            if match is None:
                return False
            del remaining[match]
    return not remaining


def differences(
    expected: dict[str, TableSpec], actual: dict[str, TableSpec]
) -> list[str]:
    """Describe schema differences in a deterministic order.

    Args:
        expected (dict[str, TableSpec]): The model definitions
        actual (dict[str, TableSpec]): The live database definitions

    Returns:
        list[str]: Human-readable differences, including expected and actual values
    """
    result = []
    for table in sorted(expected.keys() | actual.keys()):
        if table not in actual:
            result.append(f"Missing table: public.{table}")
            continue
        if table not in expected:
            result.append(f"Extra table: public.{table}")
            continue
        want, have = expected[table], actual[table]
        for col in sorted(want.columns.keys() | have.columns.keys()):
            if col not in have.columns:
                result.append(f"Missing column: {table}.{col}")
            elif col not in want.columns:
                result.append(f"Extra column: {table}.{col}")
            elif want.columns[col] != have.columns[col]:
                result.append(
                    f"Column mismatch: {table}.{col}; expected={want.columns[col]}; actual={have.columns[col]}"
                )
        if not _constraint_matches(want, have):
            result.append(
                f"Constraint mismatch: {table}; expected={want.constraints}; actual={have.constraints}"
            )
        if want.indexes != have.indexes:
            result.append(
                f"Index mismatch: {table}; expected={want.indexes}; actual={have.indexes}"
            )
    return result


async def _add_only(
    connection: asyncpg.Connection,
    expected: dict[str, TableSpec],
    actual: dict[str, TableSpec],
) -> None:
    """Apply only new tables and columns, isolating failed additions with savepoints.

    Args:
        connection (asyncpg.Connection): The transaction's connection
        expected (dict[str, TableSpec]): The declared schema
        actual (dict[str, TableSpec]): The original catalog snapshot
    """
    for model in sort_table_classes([s.model for s in expected.values()]):
        name = model._meta.tablename
        spec = expected[name]
        if name not in actual:
            try:
                async with connection.transaction():
                    for statement in model.create_table().ddl:
                        await connection.execute(statement)
                logger.info("Created table public.%s", name)
            except asyncpg.PostgresError as exception:
                logger.warning("Skipped creation of %s: %s", name, exception)
            continue
        for col in spec.columns:
            if col in actual[name].columns:
                continue
            try:
                async with connection.transaction():
                    # Inline keys and foreign keys belong to the newly added column.
                    model_column = next(
                        column
                        for column in model._meta.columns
                        if column._meta.db_column_name == col
                    )
                    await connection.execute(
                        f"ALTER TABLE {qualified(name)} ADD COLUMN {model_column.ddl}"
                    )
                    if model_column._meta.index:
                        await connection.execute(spec.index_sql[f"{name}_{col}"])
                logger.info("Added column %s.%s", name, col)
            except asyncpg.PostgresError as exception:
                logger.warning("Skipped addition of %s.%s: %s", name, col, exception)


def _dependent_tables(
    names: set[str], expected: dict[str, TableSpec], actual: dict[str, TableSpec]
) -> set[str]:
    """Find tables whose data depends on the tables being reset.

    Args:
        names (set[str]): The initially affected tables
        expected (dict[str, TableSpec]): The declared schema
        actual (dict[str, TableSpec]): The original catalog snapshot

    Returns:
        set[str]: The recursive dependency closure
    """
    closure = set(names)
    while True:
        previous = set(closure)
        for name in expected:
            references = expected[name].references | (
                actual[name].references if name in actual else set()
            )
            if references & closure:
                closure.add(name)
        if closure == previous:
            return closure


async def _create_bare(
    connection: asyncpg.Connection, name: str, spec: TableSpec
) -> None:
    """Create a table before restoring its keys and indexes.

    Args:
        connection (asyncpg.Connection): The transaction's connection
        name (str): The physical table name
        spec (TableSpec): The declared columns
    """
    await connection.execute(
        f"CREATE TABLE {qualified(name)} ({', '.join(spec.definitions.values())})"
    )


async def _rebuild(
    connection: asyncpg.Connection,
    names: set[str],
    expected: dict[str, TableSpec],
    actual: dict[str, TableSpec],
) -> set[str]:
    """Reset affected tables and dependent data with restrictive drops.

    Args:
        connection (asyncpg.Connection): The transaction's connection
        names (set[str]): The tables requiring a reset
        expected (dict[str, TableSpec]): The declared schema
        actual (dict[str, TableSpec]): The original catalog snapshot

    Returns:
        set[str]: The tables rebuilt by this operation
    """
    closure = _dependent_tables(names, expected, actual)
    logger.warning(
        "Hard schema migration: rebuilding tables and discarding their data: %s",
        ", ".join(sorted(closure)),
    )
    # Foreign keys are absent while rebuilding. RESTRICT protects out-of-scope dependencies.
    for name in sorted(closure):
        await connection.execute(f"DROP TABLE IF EXISTS {qualified(name)}")
    for name in sorted(closure):
        await _create_bare(connection, name, expected[name])
    return closure


async def _alter_table(
    connection: asyncpg.Connection, name: str, want: TableSpec, have: TableSpec
) -> None:
    """Reconcile column definitions, preserving existing rows where possible.

    Args:
        connection (asyncpg.Connection): The transaction's connection
        name (str): The physical table name
        want (TableSpec): The declared table
        have (TableSpec): The original table

    Raises:
        ValueError: Raised when changing generated columns requires a table reset
    """
    for col in sorted(have.columns.keys() - want.columns.keys()):
        await connection.execute(
            f"ALTER TABLE {qualified(name)} DROP COLUMN {quote(col)}"
        )
    for col, desired in want.columns.items():
        prefix = f"ALTER TABLE {qualified(name)} ALTER COLUMN {quote(col)}"
        if col not in have.columns:
            await connection.execute(
                f"ALTER TABLE {qualified(name)} ADD COLUMN {want.definitions[col]}"
            )
            continue
        current = have.columns[col]
        if desired == current:
            continue
        if desired.serial != current.serial or desired.generated != current.generated:
            raise ValueError(f"Generated/serial definition changed: {name}.{col}")
        if desired.serial and desired.sequence != current.sequence:
            sequence_name = await connection.fetchval(
                "SELECT pg_get_serial_sequence($1,$2)", qualified(name), col
            )
            sequence_type, start, increment, minimum, maximum, cache, cycle = (
                desired.sequence
            )
            await connection.execute(
                f"ALTER SEQUENCE {sequence_name} AS {sequence_type} START WITH {start} INCREMENT BY {increment} MINVALUE {minimum} MAXVALUE {maximum} CACHE {cache} {'CYCLE' if cycle else 'NO CYCLE'}"
            )
        if desired.sql_type != current.sql_type:
            await connection.execute(f"{prefix} DROP DEFAULT")
            expression = f"{quote(col)}::{desired.sql_type}"
            if (current.sql_type, desired.sql_type) in (
                ("timestamp without time zone", "timestamp with time zone"),
                ("timestamp with time zone", "timestamp without time zone"),
            ):
                expression = f"{quote(col)} AT TIME ZONE 'UTC'"
            await connection.execute(
                f"{prefix} TYPE {desired.sql_type} USING {expression}"
            )
        if not desired.serial:
            await connection.execute(f"{prefix} SET DEFAULT {want.defaults[col]}")
        await connection.execute(
            f"{prefix} {'DROP' if desired.nullable else 'SET'} NOT NULL"
        )


async def _hard(
    connection: asyncpg.Connection,
    expected: dict[str, TableSpec],
    actual: dict[str, TableSpec],
) -> None:
    """Reconcile all public tables, rebuilding only when alterations fail.

    Args:
        connection (asyncpg.Connection): The transaction's connection
        expected (dict[str, TableSpec]): The declared schema
        actual (dict[str, TableSpec]): The original catalog snapshot

    Raises:
        PostgresError: Re-raises an unrecoverable constraint restoration failure
    """
    changed = {
        name
        for name in expected.keys() | actual.keys()
        if differences(
            {name: expected[name]} if name in expected else {},
            {name: actual[name]} if name in actual else {},
        )
    }
    affected = _dependent_tables(changed, actual | expected, actual)
    expected = {name: spec for name, spec in expected.items() if name in affected}
    actual = {name: spec for name, spec in actual.items() if name in affected}
    # Lock existing tables so other writers cannot change data during reconciliation.
    if actual:
        await connection.execute(
            f"LOCK TABLE {', '.join(qualified(n) for n in sorted(actual))} IN ACCESS EXCLUSIVE MODE"
        )
    # Remove foreign keys first, then keys and checks, so column operations are independent.
    for foreign_only in (True, False):
        for name, spec in actual.items():
            for constraint, definition in spec.constraints.items():
                if definition.startswith("foreign key") == foreign_only:
                    await connection.execute(
                        f"ALTER TABLE {qualified(name)} DROP CONSTRAINT {quote(constraint)}"
                    )
    for spec in actual.values():
        for index in spec.indexes:
            await connection.execute(f"DROP INDEX {qualified(index)}")
    for name in sorted(actual.keys() - expected.keys()):
        logger.warning("Hard schema migration: deleting extra table public.%s", name)
        await connection.execute(f"DROP TABLE {qualified(name)}")
    rebuilt = set()
    for name, spec in expected.items():
        if name in rebuilt:
            continue
        if name not in actual:
            await _create_bare(connection, name, spec)
            logger.info("Created table public.%s", name)
            continue
        try:
            async with connection.transaction():
                await _alter_table(connection, name, spec, actual[name])
                logger.info("Reconciled table public.%s", name)
        except (asyncpg.PostgresError, ValueError) as exception:
            logger.warning("Cannot alter %s in place: %s", name, exception)
            rebuilt |= await _rebuild(connection, {name}, expected, actual)
    # Constraint failures can require data resets. Retry from a constraint-free state.
    while True:
        failed_table = None
        try:
            async with connection.transaction():
                for foreign_only in (False, True):
                    for name, spec in expected.items():
                        failed_table = name
                        for constraint, sql in spec.constraint_sql.items():
                            if sql.startswith("FOREIGN KEY") == foreign_only:
                                await connection.execute(
                                    f"ALTER TABLE {qualified(name)} ADD CONSTRAINT {quote(constraint)} {sql}"
                                )
            break
        except asyncpg.PostgresError:
            if failed_table in rebuilt:
                raise
            rebuilt |= await _rebuild(connection, {failed_table}, expected, actual)
    for spec in expected.values():
        for statement in spec.index_sql.values():
            await connection.execute(statement)


async def synchronize_schema(
    engine: PostgresEngine, mode: SchemaMode | None = None
) -> SchemaSyncResult:
    """Compare and synchronize public tables using one locked transaction.

    Args:
        engine (PostgresEngine): The connected Piccolo engine
        mode (SchemaMode | None): The mode override, or None to read the environment

    Raises:
        RuntimeError: Raised if hard mode cannot produce the declared schema

    Returns:
        SchemaSyncResult: The initial and remaining schema differences
    """
    mode = configured_mode() if mode is None else SchemaMode(mode)
    logger.info(
        "Startup schema synchronization: mode=%s (%s)", mode.value, mode.name.lower()
    )
    models = table_finder(["database.schema"], exclude_imported=True)
    expected = expected_schema(models)
    async with engine.pool.acquire() as connection:
        async with connection.transaction(readonly=mode == SchemaMode.REPORT):
            await connection.execute("SELECT pg_advisory_xact_lock($1)", LOCK_ID)
            await connection.execute("SET LOCAL search_path TO public, pg_catalog")
            actual = await inspect_schema(connection)
            initial = differences(expected, actual)
            if not initial:
                logger.info("Database schema matches the declared models")
                return SchemaSyncResult(mode, [], [])
            logger.warning(
                "Database schema is mismatched (%d differences)", len(initial)
            )
            for difference in initial:
                logger.warning("%s", difference)
            if mode == SchemaMode.REPORT:
                return SchemaSyncResult(mode, initial, initial)
            if mode == SchemaMode.ADD:
                await _add_only(connection, expected, actual)
            else:
                await _hard(connection, expected, actual)
            remaining = differences(expected, await inspect_schema(connection))
            for difference in remaining:
                logger.warning("Remaining schema mismatch: %s", difference)
            if mode == SchemaMode.HARD and remaining:
                raise RuntimeError(
                    "Hard schema migration did not produce the declared schema"
                )
            logger.info(
                "Schema synchronization finished: %d remaining differences",
                len(remaining),
            )
            return SchemaSyncResult(mode, initial, remaining)
