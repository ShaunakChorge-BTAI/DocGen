"""MySQL-specific schema extraction adapter."""

import logging
from datetime import datetime
from typing import List

from .schema_adapter import (
    SchemaAdapter, SchemaMetadata, SchemaTable, SchemaColumn,
    SchemaProcedure, SchemaView, SchemaIndex
)

logger = logging.getLogger(__name__)


class MySQLSchemaAdapter(SchemaAdapter):
    """Extract schema metadata from MySQL/MariaDB."""

    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema."""
        tables = self.extract_tables()
        procedures = self.extract_procedures()
        views = self.extract_views()
        indexes = self.extract_indexes()

        return SchemaMetadata(
            db_name=self.driver.db_entry.database_name,
            db_type='mysql',
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
            AND TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
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
            logger.error(f"Error extracting MySQL tables: {e}")
            return []

    def _get_table_columns(self, table_name: str, schema_name: str) -> List[SchemaColumn]:
        """Get columns for a specific table."""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                COLUMN_TYPE as data_type,
                IS_NULLABLE as is_nullable,
                CHARACTER_MAXIMUM_LENGTH as char_max_length,
                COLUMN_DEFAULT as column_default,
                COLUMN_KEY as col_key
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
            ORDER BY ORDINAL_POSITION
        """
        try:
            results = self.driver.execute_query(sql, (table_name, schema_name))

            columns = []
            for row in results:
                col = SchemaColumn(
                    name=row['column_name'],
                    data_type=row['data_type'],
                    is_nullable=row['is_nullable'] == 'YES',
                    is_primary_key=row.get('col_key') == 'PRI',
                    character_max_length=row.get('char_max_length'),
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
                ROUTINE_NAME as routine_name,
                ROUTINE_SCHEMA as routine_schema
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
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
            logger.error(f"Error extracting MySQL procedures: {e}")
            return []

    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        sql = """
            SELECT
                TABLE_NAME as table_name,
                TABLE_SCHEMA as table_schema
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'VIEW'
            AND TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
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
            logger.error(f"Error extracting MySQL views: {e}")
            return []

    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes."""
        sql = """
            SELECT
                INDEX_NAME as index_name,
                TABLE_NAME as table_name,
                TABLE_SCHEMA as table_schema,
                SEQ_IN_INDEX,
                NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY TABLE_NAME, INDEX_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            # Group by index
            indexes_dict = {}
            for row in results:
                idx_name = row['index_name']
                if idx_name not in indexes_dict:
                    indexes_dict[idx_name] = SchemaIndex(
                        name=idx_name,
                        table_name=row['table_name'],
                        table_schema=row['table_schema'],
                        columns=[],
                        is_unique=row['NON_UNIQUE'] == 0
                    )

            return list(indexes_dict.values())
        except Exception as e:
            logger.error(f"Error extracting MySQL indexes: {e}")
            return []
