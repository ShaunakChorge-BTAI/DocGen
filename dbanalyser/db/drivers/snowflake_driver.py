"""Snowflake driver using snowflake-connector-python."""

import logging
from typing import Any, List, Dict, Optional
from .base import DatabaseDriver, TableDef, ColumnDef, ProcedureDef, ViewDef, IndexDef

logger = logging.getLogger(__name__)


class SnowflakeDriver(DatabaseDriver):
    """Snowflake driver using snowflake-connector-python."""

    def __init__(self, db_entry: Any):
        super().__init__(db_entry)
        self.connection = None

    def test_connection(self) -> bool:
        """Test Snowflake connection."""
        try:
            import snowflake.connector
        except ImportError:
            logger.error("snowflake-connector-python package not installed. Install with: pip install snowflake-connector-python")
            return False

        try:
            conn = snowflake.connector.connect(
                user=self.db_entry.username,
                password=self.db_entry.password,
                account=self.db_entry.host,  # Snowflake account ID
                warehouse=self.db_entry.snowflake_warehouse,
                database=self.db_entry.database_name
            )
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Snowflake connection test failed: {e}")
            return False

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Snowflake configuration."""
        if not self.db_entry.host:
            return False, "Account ID is required"
        if not self.db_entry.username:
            return False, "Username is required"
        if not self.db_entry.password:
            return False, "Password is required"
        if not self.db_entry.snowflake_warehouse:
            return False, "Warehouse is required"
        if not self.db_entry.database_name:
            return False, "Database is required"
        return True, None

    def get_connection_string(self) -> str:
        """Return Snowflake connection string."""
        return (f"snowflake://{self.db_entry.username}:{self.db_entry.password}"
                f"@{self.db_entry.host}/{self.db_entry.database_name}")

    def connect(self) -> Any:
        """Establish Snowflake connection."""
        import snowflake.connector
        self.connection = snowflake.connector.connect(
            user=self.db_entry.username,
            password=self.db_entry.password,
            account=self.db_entry.host,
            warehouse=self.db_entry.snowflake_warehouse,
            database=self.db_entry.database_name,
            role=self.db_entry.snowflake_role or 'ACCOUNTADMIN'
        )
        return self.connection

    def disconnect(self) -> None:
        """Close connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute query and return results."""
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        finally:
            cursor.close()

    def list_tables(self) -> List[TableDef]:
        """List all tables (Snowflake)."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [TableDef(name=r['name'], schema=r['schema']) for r in results]

    def get_table_columns(self, table_name: str, schema: str = 'PUBLIC') -> List[ColumnDef]:
        """Get columns for a table (Snowflake)."""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE as is_nullable
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
            ORDER BY ORDINAL_POSITION
        """
        results = self.execute_query(sql, (table_name.upper(), schema.upper()))
        return [
            ColumnDef(
                table_name=table_name,
                table_schema=schema,
                column_name=r['column_name'],
                data_type=r['data_type'],
                is_nullable=r['is_nullable'] == 'YES'
            )
            for r in results
        ]

    def list_procedures(self) -> List[ProcedureDef]:
        """List all procedures and functions (Snowflake)."""
        sql = """
            SELECT
                PROCEDURE_NAME as name,
                PROCEDURE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.PROCEDURES
            WHERE PROCEDURE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY PROCEDURE_SCHEMA, PROCEDURE_NAME
        """
        results = self.execute_query(sql)
        return [ProcedureDef(name=r['name'], schema=r['schema']) for r in results]

    def list_views(self) -> List[ViewDef]:
        """List all views (Snowflake)."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'VIEW'
            AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [ViewDef(name=r['name'], schema=r['schema']) for r in results]

    def list_indexes(self) -> List[IndexDef]:
        """List all indexes (Snowflake).

        Note: Snowflake does not have traditional indexes like other databases.
        This returns an empty list.
        """
        # Snowflake doesn't have traditional indexes; uses clustering keys instead
        return []
