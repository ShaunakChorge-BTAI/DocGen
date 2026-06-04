"""Factory for creating appropriate database driver instances."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .drivers.base import DatabaseDriver

logger = logging.getLogger(__name__)


def get_driver(db_entry: 'DatabaseEntry') -> 'DatabaseDriver':
    """Create and return appropriate driver for database type.

    Args:
        db_entry: DatabaseEntry config object

    Returns:
        Appropriate DatabaseDriver instance

    Raises:
        ValueError: If unsupported db_type
    """
    db_type = db_entry.db_type.lower()

    if db_type == 'mssql':
        from .drivers.mssql_driver import MSSQLDriver
        return MSSQLDriver(db_entry)
    elif db_type == 'oracle':
        from .drivers.oracle_driver import OracleDriver
        return OracleDriver(db_entry)
    elif db_type == 'postgresql':
        from .drivers.postgresql_driver import PostgreSQLDriver
        return PostgreSQLDriver(db_entry)
    elif db_type == 'mysql':
        from .drivers.mysql_driver import MySQLDriver
        return MySQLDriver(db_entry)
    elif db_type == 'snowflake':
        from .drivers.snowflake_driver import SnowflakeDriver
        return SnowflakeDriver(db_entry)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_default_port(db_type: str) -> int:
    """Get default port for database type.

    Args:
        db_type: Database type string

    Returns:
        Default port number
    """
    ports = {
        'mssql': 1433,
        'oracle': 1521,
        'postgresql': 5432,
        'mysql': 3306,
        'snowflake': 443,
        'mariadb': 3306,
    }
    return ports.get(db_type.lower(), 5432)


# Type import for full type hints
try:
    from .config import DatabaseEntry
except ImportError:
    pass
