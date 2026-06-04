"""Snowflake-specific schema extraction adapter."""

import logging
from datetime import datetime
from typing import List

from .schema_adapter import (
    SchemaAdapter, SchemaMetadata, SchemaTable, SchemaColumn,
    SchemaProcedure, SchemaView, SchemaIndex
)

logger = logging.getLogger(__name__)


class SnowflakeSchemaAdapter(SchemaAdapter):
    """Extract schema metadata from Snowflake."""

    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema."""
        tables = self.extract_tables()
        procedures = self.extract_procedures()
        views = self.extract_views()
        indexes = self.extract_indexes()

        return SchemaMetadata(
            db_name=self.driver.db_entry.database_name,
            db_type='snowflake',
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
                TABLE_NAME as table_name,
                TABLE_SCHEMA as table_schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
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
            logger.error(f"Error extracting Snowflake tables: {e}")
            return []

    def _get_table_columns(self, table_name: str, schema_name: str) -> List[SchemaColumn]:
        """Get columns for a specific table."""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE as is_nullable,
                CHARACTER_MAXIMUM_LENGTH as char_max_length
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
            ORDER BY ORDINAL_POSITION
        """
        try:
            results = self.driver.execute_query(sql, (table_name.upper(), schema_name.upper()))

            columns = []
            for row in results:
                col = SchemaColumn(
                    name=row['column_name'],
                    data_type=row['data_type'],
                    is_nullable=row['is_nullable'] == 'YES',
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
                PROCEDURE_NAME as procedure_name,
                PROCEDURE_SCHEMA as procedure_schema
            FROM INFORMATION_SCHEMA.PROCEDURES
            WHERE PROCEDURE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY PROCEDURE_SCHEMA, PROCEDURE_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            procedures = [
                SchemaProcedure(
                    name=row['procedure_name'],
                    schema=row['procedure_schema']
                )
                for row in results
            ]
            return procedures
        except Exception as e:
            logger.error(f"Error extracting Snowflake procedures: {e}")
            return []

    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        sql = """
            SELECT
                TABLE_NAME as table_name,
                TABLE_SCHEMA as table_schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'VIEW'
            AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
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
            logger.error(f"Error extracting Snowflake views: {e}")
            return []

    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes (Snowflake doesn't have traditional indexes)."""
        # Snowflake doesn't have traditional indexes like other databases
        # Uses clustering keys instead, which are not represented as indexes
        return []
