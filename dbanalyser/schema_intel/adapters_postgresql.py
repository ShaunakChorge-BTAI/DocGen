"""PostgreSQL-specific schema extraction adapter."""

import logging
from datetime import datetime
from typing import List

from .schema_adapter import (
    SchemaAdapter, SchemaMetadata, SchemaTable, SchemaColumn,
    SchemaProcedure, SchemaView, SchemaIndex
)

logger = logging.getLogger(__name__)


class PostgreSQLSchemaAdapter(SchemaAdapter):
    """Extract schema metadata from PostgreSQL."""

    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema."""
        tables = self.extract_tables()
        procedures = self.extract_procedures()
        views = self.extract_views()
        indexes = self.extract_indexes()

        return SchemaMetadata(
            db_name=self.driver.db_entry.database_name,
            db_type='postgresql',
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
                tablename as table_name,
                schemaname as table_schema
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
        """
        try:
            self.driver.connect()
            results = self.driver.execute_query(sql)

            tables = []
            for row in results:
                table_name = row['table_name']
                schema_name = row['table_schema']
                columns = self._get_table_columns(table_name, schema_name)

                table = SchemaTable(
                    name=table_name,
                    schema=schema_name,
                    columns=columns
                )
                tables.append(table)

            return tables
        except Exception as e:
            logger.error(f"Error extracting PostgreSQL tables: {e}")
            return []

    def _get_table_columns(self, table_name: str, schema_name: str) -> List[SchemaColumn]:
        """Get columns for a specific table."""
        sql = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                character_maximum_length,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = %s
            ORDER BY ordinal_position
        """
        try:
            results = self.driver.execute_query(sql, (table_name, schema_name))

            columns = []
            for row in results:
                col = SchemaColumn(
                    name=row['column_name'],
                    data_type=row['data_type'],
                    is_nullable=row['is_nullable'] == 'YES',
                    character_max_length=row.get('character_maximum_length'),
                    default_value=row.get('column_default')
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
                routinename as routine_name,
                routine_schema as routine_schema
            FROM information_schema.routines
            WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY routine_schema, routinename
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
            logger.error(f"Error extracting PostgreSQL procedures: {e}")
            return []

    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        sql = """
            SELECT
                viewname as view_name,
                schemaname as view_schema
            FROM pg_views
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, viewname
        """
        try:
            results = self.driver.execute_query(sql)
            views = [
                SchemaView(
                    name=row['view_name'],
                    schema=row['view_schema']
                )
                for row in results
            ]
            return views
        except Exception as e:
            logger.error(f"Error extracting PostgreSQL views: {e}")
            return []

    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes."""
        sql = """
            SELECT
                indexname as index_name,
                tablename as table_name,
                schemaname as table_schema,
                indexdef
            FROM pg_indexes
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY tablename, indexname
        """
        try:
            results = self.driver.execute_query(sql)
            indexes = [
                SchemaIndex(
                    name=row['index_name'],
                    table_name=row['table_name'],
                    table_schema=row['table_schema'],
                    columns=[],
                    is_unique='UNIQUE' in (row.get('indexdef') or '')
                )
                for row in results
            ]
            return indexes
        except Exception as e:
            logger.error(f"Error extracting PostgreSQL indexes: {e}")
            return []
