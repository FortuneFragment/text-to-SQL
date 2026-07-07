"""SQL Server dialect helpers for Text2SQL.

The queried business database is SQL Server only. The generation, validation,
repair, and execution pipeline therefore uses T-SQL directly instead of
generating MySQL first and transpiling at execution time.
"""

from __future__ import annotations


DB_TYPE_MYSQL = "mysql"  # Kept only for legacy/system-database references.
DB_TYPE_SQLSERVER = "sqlserver"

SUPPORTED_DB_TYPES: tuple[str, ...] = (DB_TYPE_SQLSERVER,)
INTERNAL_SQLGLOT_DIALECT = "tsql"

_DB_TYPE_ALIASES: dict[str, str] = {
    "sqlserver": DB_TYPE_SQLSERVER,
    "sql_server": DB_TYPE_SQLSERVER,
    "sql server": DB_TYPE_SQLSERVER,
    "mssql": DB_TYPE_SQLSERVER,
    "ms sql": DB_TYPE_SQLSERVER,
    "microsoft sql server": DB_TYPE_SQLSERVER,
}

_SQLALCHEMY_DRIVER: dict[str, str] = {
    DB_TYPE_SQLSERVER: "mssql+pymssql",
}

_DEFAULT_PORT: dict[str, int] = {
    DB_TYPE_SQLSERVER: 1433,
}

_DEFAULT_CHARSET: dict[str, str] = {
    DB_TYPE_SQLSERVER: "UTF-8",
}


def normalize_db_type(db_type: str | None) -> str:
    key = str(db_type or "").strip().lower()
    return _DB_TYPE_ALIASES.get(key, key)


def is_supported_db_type(db_type: str | None) -> bool:
    return normalize_db_type(db_type) in SUPPORTED_DB_TYPES


def sqlglot_dialect_for(db_type: str | None = None) -> str:
    return INTERNAL_SQLGLOT_DIALECT


def sqlalchemy_driver_for(db_type: str | None) -> str:
    return _SQLALCHEMY_DRIVER[DB_TYPE_SQLSERVER]


def default_port_for(db_type: str | None) -> int:
    return _DEFAULT_PORT[DB_TYPE_SQLSERVER]


def default_charset_for(db_type: str | None) -> str:
    return _DEFAULT_CHARSET[DB_TYPE_SQLSERVER]
