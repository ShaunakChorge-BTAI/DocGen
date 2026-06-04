"""Oracle-specific schema extraction adapter."""

import logging
from datetime import datetime
from typing import List

from .schema_adapter import (
    SchemaAdapter, SchemaMetadata, SchemaTable, SchemaColumn,
    SchemaProcedure, SchemaView, SchemaIndex
)

logger = logging.getLogger(__name__)


class OracleSchemaAdapter(SchemaAdapter):
    """Extract schema metadata from Oracle Database."""

    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema."""
        tables = self.extract_tables()
        procedures = self.extract_procedures()
        views = self.extract_views()
        indexes = self.extract_indexes()

        return SchemaMetadata(
            db_name=self.driver.db_entry.database_name or self.driver.db_entry.oracle_sid_or_service,
            db_type='oracle',
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
                OWNER as owner
            FROM ALL_TABLES
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_', 'MDSYS', 'OLAPSYS')
            ORDER BY OWNER, TABLE_NAME
        """
        try:
            self.driver.connect()
            results = self.driver.execute_query(sql)

            tables = []
            for row in results:
                table_name = row['table_name']
                owner = row['owner']
                columns = self._get_table_columns(table_name, owner)

                table = SchemaTable(
                    name=table_name,
                    schema=owner,
                    columns=columns
                )
                tables.append(table)

            return tables
        except Exception as e:
            logger.error(f"Error extracting Oracle tables: {e}")
            return []

    def _get_table_columns(self, table_name: str, owner: str) -> List[SchemaColumn]:
        """Get columns for a specific table."""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                NULLABLE as is_nullable,
                DATA_LENGTH as char_max_length
            FROM ALL_TAB_COLUMNS
            WHERE TABLE_NAME = :table_name AND OWNER = :owner
            ORDER BY COLUMN_ID
        """
        try:
            results = self.driver.execute_query(sql, {
                'table_name': table_name,
                'owner': owner
            })

            columns = []
            for row in results:
                col = SchemaColumn(
                    name=row['column_name'],
                    data_type=row['data_type'],
                    is_nullable=row['is_nullable'] == 'Y',
                    character_max_length=row.get('char_max_length')
                )
                columns.append(col)

            return columns
        except Exception as e:
            logger.error(f"Error extracting columns for {owner}.{table_name}: {e}")
            return []

    def extract_procedures(self) -> List[SchemaProcedure]:
        """Extract all stored procedures and functions."""
        sql = """
            SELECT
                OBJECT_NAME as object_name,
                OWNER as owner
            FROM ALL_PROCEDURES
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_', 'MDSYS', 'OLAPSYS')
            ORDER BY OWNER, OBJECT_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            procedures = [
                SchemaProcedure(
                    name=row['object_name'],
                    schema=row['owner']
                )
                for row in results
            ]
            return procedures
        except Exception as e:
            logger.error(f"Error extracting Oracle procedures: {e}")
            return []

    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        sql = """
            SELECT
                VIEW_NAME as view_name,
                OWNER as owner
            FROM ALL_VIEWS
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_', 'MDSYS', 'OLAPSYS')
            ORDER BY OWNER, VIEW_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            views = [
                SchemaView(
                    name=row['view_name'],
                    schema=row['owner']
                )
                for row in results
            ]
            return views
        except Exception as e:
            logger.error(f"Error extracting Oracle views: {e}")
            return []

    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes."""
        sql = """
            SELECT
                INDEX_NAME as index_name,
                TABLE_NAME as table_name,
                TABLE_OWNER as table_owner,
                UNIQUENESS
            FROM ALL_INDEXES
            WHERE TABLE_OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_', 'MDSYS', 'OLAPSYS')
            ORDER BY TABLE_NAME, INDEX_NAME
        """
        try:
            results = self.driver.execute_query(sql)
            indexes = [
                SchemaIndex(
                    name=row['index_name'],
                    table_name=row['table_name'],
                    table_schema=row['table_owner'],
                    columns=[],
                    is_unique=row['UNIQUENESS'] == 'UNIQUE'
                )
                for row in results
            ]
            return indexes
        except Exception as e:
            logger.error(f"Error extracting Oracle indexes: {e}")
            return []
