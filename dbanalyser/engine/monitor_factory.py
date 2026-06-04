"""Factory for creating appropriate live monitor adapter instances."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .live_monitor import LiveMonitorAdapter

logger = logging.getLogger(__name__)


def get_monitor(db_type: str, driver: Any) -> 'LiveMonitorAdapter':
    """Create and return appropriate live monitor adapter for database type.

    Args:
        db_type: Database type string (mssql, oracle, postgresql, mysql, snowflake)
        driver: DatabaseDriver instance

    Returns:
        Appropriate LiveMonitorAdapter instance

    Raises:
        ValueError: If unsupported db_type
    """
    db_type = db_type.lower()

    if db_type == 'mssql':
        from .monitors.mssql_monitor import MSSQLMonitorAdapter
        return MSSQLMonitorAdapter(driver)
    elif db_type == 'oracle':
        from .monitors.oracle_monitor import OracleMonitorAdapter
        return OracleMonitorAdapter(driver)
    elif db_type == 'postgresql':
        from .monitors.postgresql_monitor import PostgreSQLMonitorAdapter
        return PostgreSQLMonitorAdapter(driver)
    elif db_type == 'mysql':
        from .monitors.mysql_monitor import MySQLMonitorAdapter
        return MySQLMonitorAdapter(driver)
    elif db_type == 'snowflake':
        from .monitors.snowflake_monitor import SnowflakeMonitorAdapter
        return SnowflakeMonitorAdapter(driver)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
