"""Microsoft SQL Server driver using pyodbc."""

import pyodbc
import logging
from typing import Any, List, Dict, Optional
from .base import DatabaseDriver, TableDef, ColumnDef, ProcedureDef, ViewDef, IndexDef

logger = logging.getLogger(__name__)


class MSSQLDriver(DatabaseDriver):
    """SQL Server driver using pyodbc."""

    def __init__(self, db_entry: Any):
        super().__init__(db_entry)
        self.connection = None

    def test_connection(self) -> bool:
        """Test SQL Server connection."""
        try:
            conn_str = self.get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=10)
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate MSSQL configuration."""
        if not self.db_entry.host:
            return False, "Host is required"
        if self.db_entry.port and (self.db_entry.port < 1 or self.db_entry.port > 65535):
            return False, "Port must be between 1 and 65535"
        if not self.db_entry.use_windows_auth and not self.db_entry.username:
            return False, "Username required for SQL Authentication"
        return True, None

    def get_connection_string(self) -> str:
        """Build SQL Server connection string."""
        if self.db_entry.connection_string:
            return self.db_entry.connection_string

        # Auto-detect best ODBC driver
        try:
            drivers = pyodbc.drivers()
            if "ODBC Driver 18 for SQL Server" in drivers:
                driver = "{ODBC Driver 18 for SQL Server}"
            elif "ODBC Driver 17 for SQL Server" in drivers:
                driver = "{ODBC Driver 17 for SQL Server}"
            else:
                driver = "{SQL Server}"
        except Exception:
            driver = "{ODBC Driver 17 for SQL Server}"

        port = self.db_entry.port or 1433
        base = f"DRIVER={driver};SERVER={self.db_entry.host},{port};DATABASE={self.db_entry.database_name};"

        if self.db_entry.use_windows_auth:
            result = base + "Trusted_Connection=yes;"
        else:
            result = base + f"UID={self.db_entry.username};PWD={self.db_entry.password};TrustServerCertificate=yes;"

        masked = result.replace(self.db_entry.password, "***") if self.db_entry.password else result
        logger.debug(f"[mssql_driver] Built connection string for {self.db_entry.name}: {masked}")
        return result

    def connect(self) -> Any:
        """Establish connection."""
        conn_str = self.get_connection_string()
        self.connection = pyodbc.connect(conn_str, timeout=30)
        return self.connection

    def disconnect(self) -> None:
        """Close connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None, as_dict: bool = True) -> List[Any]:
        """Execute query and return results."""
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            if as_dict:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return results
            else:
                return cursor.fetchall()
        finally:
            cursor.close()

    def list_tables(self) -> List[TableDef]:
        """List all tables."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [TableDef(name=r['name'], schema=r['schema']) for r in results]

    def get_table_columns(self, table_name: str, schema: str = 'dbo') -> List[ColumnDef]:
        """Get columns for a table."""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE,
                COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsIdentity') as is_pk
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
            ORDER BY ORDINAL_POSITION
        """
        results = self.execute_query(sql, {'param1': table_name, 'param2': schema})
        return [
            ColumnDef(
                table_name=table_name,
                table_schema=schema,
                column_name=r['column_name'],
                data_type=r['data_type'],
                is_nullable=r['IS_NULLABLE'] == 'YES',
                is_primary_key=bool(r.get('is_pk'))
            )
            for r in results
        ]

    def list_procedures(self) -> List[ProcedureDef]:
        """List all stored procedures and functions."""
        sql = """
            SELECT
                ROUTINE_NAME as name,
                ROUTINE_SCHEMA as schema,
                ROUTINE_TYPE
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
        """
        results = self.execute_query(sql)
        return [ProcedureDef(name=r['name'], schema=r['schema']) for r in results]

    def list_views(self) -> List[ViewDef]:
        """List all views."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'VIEW'
            AND TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [ViewDef(name=r['name'], schema=r['schema']) for r in results]

    def list_indexes(self) -> List[IndexDef]:
        """List all indexes."""
        sql = """
            SELECT
                i.name as index_name,
                t.name as table_name,
                SCHEMA_NAME(t.schema_id) as table_schema,
                i.is_primary_key,
                i.is_unique
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            WHERE i.name IS NOT NULL
            AND t.is_ms_shipped = 0
            ORDER BY t.name, i.name
        """
        results = self.execute_query(sql)
        return [
            IndexDef(
                name=r['index_name'],
                table_name=r['table_name'],
                table_schema=r['table_schema'],
                columns=[],  # SQL Server requires second query to get columns
                is_primary=r['is_primary_key'],
                is_unique=r['is_unique']
            )
            for r in results
        ]
