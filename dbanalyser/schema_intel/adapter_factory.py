"""Factory for creating appropriate schema adapter instances."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema_adapter import SchemaAdapter

logger = logging.getLogger(__name__)


def get_schema_adapter(db_type: str, driver: Any) -> 'SchemaAdapter':
    """Create and return appropriate schema adapter for database type.

    Args:
        db_type: Database type string (mssql, oracle, postgresql, mysql, snowflake)
        driver: DatabaseDriver instance

    Returns:
        Appropriate SchemaAdapter instance

    Raises:
        ValueError: If unsupported db_type
    """
    db_type = db_type.lower()

    if db_type == 'mssql':
        from .adapters_mssql import MSSQLSchemaAdapter
        return MSSQLSchemaAdapter(driver)
    elif db_type == 'oracle':
        from .adapters_oracle import OracleSchemaAdapter
        return OracleSchemaAdapter(driver)
    elif db_type == 'postgresql':
        from .adapters_postgresql import PostgreSQLSchemaAdapter
        return PostgreSQLSchemaAdapter(driver)
    elif db_type == 'mysql':
        from .adapters_mysql import MySQLSchemaAdapter
        return MySQLSchemaAdapter(driver)
    elif db_type == 'snowflake':
        from .adapters_snowflake import SnowflakeSchemaAdapter
        return SnowflakeSchemaAdapter(driver)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
