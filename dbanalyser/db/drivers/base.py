"""Base driver abstraction for multi-database support."""

from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from dataclasses import dataclass


@dataclass
class TableDef:
    """Table definition."""
    name: str
    schema: str
    row_count: Optional[int] = None
    size_kb: Optional[float] = None


@dataclass
class ColumnDef:
    """Column definition."""
    table_name: str
    table_schema: str
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False


@dataclass
class ProcedureDef:
    """Stored procedure/function definition."""
    name: str
    schema: str
    definition: Optional[str] = None


@dataclass
class ViewDef:
    """View definition."""
    name: str
    schema: str
    definition: Optional[str] = None


@dataclass
class IndexDef:
    """Index definition."""
    name: str
    table_name: str
    table_schema: str
    columns: List[str]
    is_unique: bool = False
    is_primary: bool = False


class DatabaseDriver(ABC):
    """Abstract base class for database drivers."""

    def __init__(self, db_entry: Any):
        """Initialize driver with database entry config.

        Args:
            db_entry: DatabaseEntry config object with connection details
        """
        self.db_entry = db_entry
        self.connection = None

    @abstractmethod
    def test_connection(self) -> bool:
        """Test database connection validity.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def connect(self) -> Any:
        """Establish database connection.

        Returns:
            Connection object (pyodbc, oracledb, psycopg2, etc.)
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of result rows as dicts
        """
        pass

    @abstractmethod
    def list_tables(self) -> List[TableDef]:
        """List all tables in database.

        Returns:
            List of TableDef objects
        """
        pass

    @abstractmethod
    def get_table_columns(self, table_name: str, schema: str = None) -> List[ColumnDef]:
        """Get columns for a table.

        Args:
            table_name: Table name
            schema: Schema name (optional, driver-dependent)

        Returns:
            List of ColumnDef objects
        """
        pass

    @abstractmethod
    def list_procedures(self) -> List[ProcedureDef]:
        """List all stored procedures/functions.

        Returns:
            List of ProcedureDef objects
        """
        pass

    @abstractmethod
    def list_views(self) -> List[ViewDef]:
        """List all views.

        Returns:
            List of ViewDef objects
        """
        pass

    @abstractmethod
    def list_indexes(self) -> List[IndexDef]:
        """List all indexes.

        Returns:
            List of IndexDef objects
        """
        pass

    @abstractmethod
    def get_connection_string(self) -> str:
        """Generate connection string for this database.

        Returns:
            Connection string appropriate for this DB type
        """
        pass

    @abstractmethod
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate database entry configuration.

        Returns:
            Tuple of (is_valid, error_message if any)
        """
        pass
