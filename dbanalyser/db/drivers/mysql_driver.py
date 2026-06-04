"""MySQL/MariaDB driver using mysql-connector-python."""

import logging
from typing import Any, List, Dict, Optional
from .base import DatabaseDriver, TableDef, ColumnDef, ProcedureDef, ViewDef, IndexDef

logger = logging.getLogger(__name__)


class MySQLDriver(DatabaseDriver):
    """MySQL/MariaDB driver using mysql-connector-python."""

    def __init__(self, db_entry: Any):
        super().__init__(db_entry)
        self.connection = None

    def test_connection(self) -> bool:
        """Test MySQL connection."""
        try:
            import mysql.connector
        except ImportError:
            logger.error("mysql-connector-python package not installed. Install with: pip install mysql-connector-python")
            return False

        try:
            conn = mysql.connector.connect(
                host=self.db_entry.host,
                port=self.db_entry.port or 3306,
                database=self.db_entry.database_name,
                user=self.db_entry.username,
                password=self.db_entry.password,
                connection_timeout=10
            )
            conn.close()
            return True
        except Exception as e:
            logger.error(f"MySQL connection test failed: {e}")
            return False

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate MySQL configuration."""
        if not self.db_entry.host:
            return False, "Host is required"
        if not self.db_entry.database_name:
            return False, "Database name is required"
        if not self.db_entry.username:
            return False, "Username is required"
        return True, None

    def get_connection_string(self) -> str:
        """Return MySQL connection string."""
        port = self.db_entry.port or 3306
        return (f"mysql://{self.db_entry.username}:{self.db_entry.password}"
                f"@{self.db_entry.host}:{port}/{self.db_entry.database_name}")

    def connect(self) -> Any:
        """Establish MySQL connection."""
        import mysql.connector
        self.connection = mysql.connector.connect(
            host=self.db_entry.host,
            port=self.db_entry.port or 3306,
            database=self.db_entry.database_name,
            user=self.db_entry.username,
            password=self.db_entry.password
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

        cursor = self.connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            results = cursor.fetchall()
            return results
        finally:
            cursor.close()

    def list_tables(self) -> List[TableDef]:
        """List all tables (MySQL)."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [TableDef(name=r['name'], schema=r['schema']) for r in results]

    def get_table_columns(self, table_name: str, schema: str = None) -> List[ColumnDef]:
        """Get columns for a table (MySQL)."""
        if not schema:
            schema = self.db_entry.database_name

        sql = """
            SELECT
                COLUMN_NAME as column_name,
                COLUMN_TYPE as data_type,
                IS_NULLABLE as is_nullable,
                COLUMN_KEY as col_key
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
            ORDER BY ORDINAL_POSITION
        """
        results = self.execute_query(sql, (table_name, schema))
        return [
            ColumnDef(
                table_name=table_name,
                table_schema=schema,
                column_name=r['column_name'],
                data_type=r['data_type'],
                is_nullable=r['is_nullable'] == 'YES',
                is_primary_key=r.get('col_key') == 'PRI'
            )
            for r in results
        ]

    def list_procedures(self) -> List[ProcedureDef]:
        """List all procedures and functions (MySQL)."""
        sql = """
            SELECT
                ROUTINE_NAME as name,
                ROUTINE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
        """
        results = self.execute_query(sql)
        return [ProcedureDef(name=r['name'], schema=r['schema']) for r in results]

    def list_views(self) -> List[ViewDef]:
        """List all views (MySQL)."""
        sql = """
            SELECT
                TABLE_NAME as name,
                TABLE_SCHEMA as schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'VIEW'
            AND TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [ViewDef(name=r['name'], schema=r['schema']) for r in results]

    def list_indexes(self) -> List[IndexDef]:
        """List all indexes (MySQL)."""
        sql = """
            SELECT
                INDEX_NAME as name,
                TABLE_NAME as table_name,
                TABLE_SCHEMA as table_schema,
                SEQ_IN_INDEX,
                NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY TABLE_NAME, INDEX_NAME
        """
        results = self.execute_query(sql)
        # Group by index name
        indexes_dict = {}
        for r in results:
            idx_name = r['name']
            if idx_name not in indexes_dict:
                indexes_dict[idx_name] = IndexDef(
                    name=idx_name,
                    table_name=r['table_name'],
                    table_schema=r['table_schema'],
                    columns=[],
                    is_unique=r['NON_UNIQUE'] == 0
                )

        return list(indexes_dict.values())
