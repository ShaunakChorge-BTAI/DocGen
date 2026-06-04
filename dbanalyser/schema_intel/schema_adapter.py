"""Schema extraction abstraction for multi-database support."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class SchemaTable:
    """Table metadata."""
    name: str
    schema: str
    row_count: Optional[int] = None
    size_kb: Optional[float] = None
    columns: List['SchemaColumn'] = field(default_factory=list)


@dataclass
class SchemaColumn:
    """Column metadata."""
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_indexed: bool = False
    default_value: Optional[str] = None
    character_max_length: Optional[int] = None


@dataclass
class SchemaProcedure:
    """Stored procedure/function metadata."""
    name: str
    schema: str
    definition: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None


@dataclass
class SchemaView:
    """View metadata."""
    name: str
    schema: str
    definition: Optional[str] = None
    columns: List[SchemaColumn] = field(default_factory=list)


@dataclass
class SchemaIndex:
    """Index metadata."""
    name: str
    table_name: str
    table_schema: str
    columns: List[str]
    is_unique: bool = False
    is_primary: bool = False
    is_clustered: bool = False


@dataclass
class SchemaMetadata:
    """Complete schema snapshot for a database."""
    db_name: str
    db_type: str
    timestamp: str  # ISO8601
    tables: List[SchemaTable] = field(default_factory=list)
    procedures: List[SchemaProcedure] = field(default_factory=list)
    views: List[SchemaView] = field(default_factory=list)
    indexes: List[SchemaIndex] = field(default_factory=list)

    @property
    def total_objects(self) -> int:
        """Total count of objects."""
        return len(self.tables) + len(self.procedures) + len(self.views) + len(self.indexes)


class SchemaAdapter(ABC):
    """Abstract base class for database-specific schema extraction."""

    def __init__(self, driver: Any):
        """Initialize adapter with a database driver.

        Args:
            driver: DatabaseDriver instance (from db.drivers)
        """
        self.driver = driver

    @abstractmethod
    def extract_schema(self) -> SchemaMetadata:
        """Extract complete schema metadata from database.

        Returns:
            SchemaMetadata object with tables, procedures, views, indexes
        """
        pass

    @abstractmethod
    def extract_tables(self) -> List[SchemaTable]:
        """Extract all tables with column metadata."""
        pass

    @abstractmethod
    def extract_procedures(self) -> List[SchemaProcedure]:
        """Extract all stored procedures and functions."""
        pass

    @abstractmethod
    def extract_views(self) -> List[SchemaView]:
        """Extract all views."""
        pass

    @abstractmethod
    def extract_indexes(self) -> List[SchemaIndex]:
        """Extract all indexes."""
        pass
