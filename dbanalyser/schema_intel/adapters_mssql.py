"""MSSQL-specific schema extraction adapter."""

import logging
from datetime import datetime
from typing import List

from .schema_adapter import (
    SchemaAdapter, SchemaMetadata, SchemaTable, SchemaColumn,
    SchemaProcedure, SchemaView, SchemaIndex
)

logger = logging.getLogger(__name__)


class MSSQLSchemaAdapter(SchemaAdapter):
    """Extract schema metadata from SQL Server."""

    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema."""
        tables = self.extract_tables()
        procedures = self.extract_procedures()
        views = self.extract_views()
        indexes = self.extract_indexes()

        return SchemaMetadata(
            db_name=self.driver.db_entry.database_name,
            db_type='mssql',
            timestamp=datetime.utcnow().isoformat(),
            tables=tables,
            procedures=procedures,
            views=views,
            indexes=indexes,
        )

    def extract_tables(self) -> List[SchemaTable]:
        """Extract all tables with columns."""
        sql = """
            SELECT
                t.TABLE_NAME as table_name,
                t.TABLE_SCHEMA as table_schema
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND t.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """
        try:
            self.driver.connect()
            results = self.driver.execute_query(sql)

            tables = []
            for row in results:
                table_name = row['table_name']
                schema_name = row['table_schema']

                # Get columns for this table
                columns = self._get_table_columns(table_name, schema_name)

                table = SchemaTable(
                    name=table_name,
                    schema=schema_name,
                    columns=columns
                )
                tables.append(table)

            return tables
        except Exception as e:
            logger.error(f"Error extracting MSSQL tables: {e}")
            return []

    def _get_table_columns(self, table_name: str, schema_name: str) -> List[SchemaColumn]:
        """Get columns for a specific table."""
        sql = """
            SELECT
                c.COLUMN_NAME as column_name,
                c.DATA_TYPE as data_type,
                c.IS_NULLABLE,
                c.CHARACTER_MAXIMUM_LENGTH as char_max_length,
                COLUMNPROPERTY(OBJECT_ID(?),'['+c.COLUMN_NAME+']','IsIdentity') as is_pk
            FROM INFORMATION_SCHEMA.COLUMNS c
            WHERE c.TABLE_NAME = ? AND c.TABLE_SCHEMA = ?
            ORDER BY c.ORDINAL_POSITION
        """
        try:
            # pyodbc / driver expects positional parameters as a sequence for '?' markers
            results = self.driver.execute_query(sql, (f"{schema_name}.{table_name}", table_name, schema_name))

            columns = []
            for row in results:
                col = SchemaColumn(
                    name=row['column_name'],
                    data_type=row['data_type'],
                    is_nullable=row['IS_NULLABLE'] == 'YES',
                    is_primary_key=bool(row.get('is_pk')),
                    character_max_length=row.get('char_max_length')
                )
                columns.append(col)

            return columns
        except Exception as e:
            logger.error(f"Error extracting columns for {schema_name}.{table_name}: {e}")
            return []

    def extract_procedures(self) -> List[SchemaProcedure]:
        """Extract all stored procedures and functions."""
        sql = """
            SELECT
                r.ROUTINE_NAME as routine_name,
                r.ROUTINE_SCHEMA as routine_schema,
                r.ROUTINE_TYPE
            FROM INFORMATION_SCHEMA.ROUTINES r
            WHERE r.ROUTINE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY r.ROUTINE_SCHEMA, r.ROUTINE_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            procedures = [
                SchemaProcedure(
                    name=row['routine_name'],
                    schema=row['routine_schema']
                )
                for row in results
            ]
            return procedures
        except Exception as e:
            logger.error(f"Error extracting MSSQL procedures: {e}")
            return []

    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        sql = """
            SELECT
                t.TABLE_NAME as table_name,
                t.TABLE_SCHEMA as table_schema
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'VIEW'
            AND t.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            views = [
                SchemaView(
                    name=row['table_name'],
                    schema=row['table_schema']
                )
                for row in results
            ]
            return views
        except Exception as e:
            logger.error(f"Error extracting MSSQL views: {e}")
            return []

    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes."""
        sql = """
            SELECT
                i.name as index_name,
                t.name as table_name,
                SCHEMA_NAME(t.schema_id) as table_schema,
                i.is_primary_key,
                i.is_unique,
                i.type
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            WHERE i.name IS NOT NULL
            AND t.is_ms_shipped = 0
            ORDER BY t.name, i.name
        """
        try:
            results = self.driver.execute_query(sql)
            indexes = [
                SchemaIndex(
                    name=row['index_name'],
                    table_name=row['table_name'],
                    table_schema=row['table_schema'],
                    columns=[],  # TODO: fetch column list per index
                    is_primary=row['is_primary_key'],
                    is_unique=row['is_unique'],
                    is_clustered=row['type'] == 1
                )
                for row in results
            ]
            return indexes
        except Exception as e:
            logger.error(f"Error extracting MSSQL indexes: {e}")
            return []
