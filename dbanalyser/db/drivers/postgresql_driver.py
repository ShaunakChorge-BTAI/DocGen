"""PostgreSQL driver using psycopg2."""

import psycopg2
import logging
from typing import Any, List, Dict, Optional
from .base import DatabaseDriver, TableDef, ColumnDef, ProcedureDef, ViewDef, IndexDef

logger = logging.getLogger(__name__)


class PostgreSQLDriver(DatabaseDriver):
    """PostgreSQL driver using psycopg2."""

    def __init__(self, db_entry: Any):
        super().__init__(db_entry)
        self.connection = None

    def test_connection(self) -> bool:
        """Test PostgreSQL connection."""
        try:
            conn = psycopg2.connect(
                host=self.db_entry.host,
                port=self.db_entry.port or 5432,
                database=self.db_entry.database_name,
                user=self.db_entry.username,
                password=self.db_entry.password,
                connect_timeout=10
            )
            conn.close()
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate PostgreSQL configuration."""
        if not self.db_entry.host:
            return False, "Host is required"
        if not self.db_entry.database_name:
            return False, "Database name is required"
        if not self.db_entry.username:
            return False, "Username is required"
        return True, None

    def get_connection_string(self) -> str:
        """Return PostgreSQL connection string."""
        port = self.db_entry.port or 5432
        return (f"postgresql://{self.db_entry.username}:{self.db_entry.password}"
                f"@{self.db_entry.host}:{port}/{self.db_entry.database_name}")

    def connect(self) -> Any:
        """Establish PostgreSQL connection."""
        self.connection = psycopg2.connect(
            host=self.db_entry.host,
            port=self.db_entry.port or 5432,
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
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = []
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        results.append(dict(row))
                    else:
                        results.append(dict(zip(columns, row)))
                return results
            else:
                # Mock psycopg2 sometimes returns dictionaries directly even when fetching all, 
                # we need to make sure we return tuples if as_dict=False
                results = []
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        results.append(tuple(row.values()))
                    else:
                        results.append(tuple(row))
                return results
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def list_tables(self) -> List[TableDef]:
        """List all tables (PostgreSQL)."""
        sql = """
            SELECT
                tablename as name,
                schemaname as schema
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
        """
        results = self.execute_query(sql)
        return [TableDef(name=r['name'], schema=r['schema']) for r in results]

    def get_table_columns(self, table_name: str, schema: str = 'public') -> List[ColumnDef]:
        """Get columns for a table (PostgreSQL)."""
        sql = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = %s
            ORDER BY ordinal_position
        """
        results = self.execute_query(sql, (table_name, schema))
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
        """List all procedures and functions (PostgreSQL)."""
        sql = """
            SELECT
                routinename as name,
                routine_schema as schema
            FROM information_schema.routines
            WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY routine_schema, routinename
        """
        results = self.execute_query(sql)
        return [ProcedureDef(name=r['name'], schema=r['schema']) for r in results]

    def list_views(self) -> List[ViewDef]:
        """List all views (PostgreSQL)."""
        sql = """
            SELECT
                viewname as name,
                schemaname as schema
            FROM pg_views
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, viewname
        """
        results = self.execute_query(sql)
        return [ViewDef(name=r['name'], schema=r['schema']) for r in results]

    def list_indexes(self) -> List[IndexDef]:
        """List all indexes (PostgreSQL)."""
        sql = """
            SELECT
                indexname as name,
                tablename as table_name,
                schemaname as table_schema,
                indexdef
            FROM pg_indexes
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY tablename, indexname
        """
        results = self.execute_query(sql)
        return [
            IndexDef(
                name=r['name'],
                table_name=r['table_name'],
                table_schema=r['table_schema'],
                columns=[],
                is_unique='UNIQUE' in (r.get('indexdef') or '')
            )
            for r in results
        ]
