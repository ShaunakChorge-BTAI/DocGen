"""Oracle Database driver (stub - to be implemented)."""

import logging
from typing import Any, List, Dict, Optional
from .base import DatabaseDriver, TableDef, ColumnDef, ProcedureDef, ViewDef, IndexDef

logger = logging.getLogger(__name__)


class OracleDriver(DatabaseDriver):
    """Oracle Database driver using oracledb."""

    def __init__(self, db_entry: Any):
        super().__init__(db_entry)
        self.connection = None

    def test_connection(self) -> bool:
        """Test Oracle connection."""
        print("[ORACLE DB TEST] Starting Oracle connection test...")
        try:
            print("[ORACLE DB TEST] Attempting to import oracledb package...")
            import oracledb
            print(f"[ORACLE DB TEST] Successfully imported oracledb version: {oracledb.__version__}")
        except ImportError:
            logger.error("oracledb package not installed. Install with: pip install oracledb")
            print("[ORACLE DB TEST] FAILED: oracledb package is not installed.")
            return False

        try:
            print("[ORACLE DB TEST] Building DSN...")
            dsn = self._build_dsn()
            print(f"[ORACLE DB TEST] DSN successfully built: {dsn}")
            
            print(f"[ORACLE DB TEST] Attempting to connect with username: '{self.db_entry.username}'...")
            conn = oracledb.connect(dsn=dsn, user=self.db_entry.username, password=self.db_entry.password)
            print(f"[ORACLE DB TEST] Connection established successfully! Oracle DB version: {getattr(conn, 'version', 'unknown')}")
            
            print("[ORACLE DB TEST] Closing test connection...")
            conn.close()
            print("[ORACLE DB TEST] Test connection closed. Test PASSED.")
            return True
        except Exception as e:
            logger.error(f"Oracle connection test failed: {e}")
            print(f"[ORACLE DB TEST] FAILED: Exception occurred during connection: {e}")
            return False

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Oracle configuration."""
        if not self.db_entry.host:
            return False, "Host is required"
        if not self.db_entry.oracle_sid_or_service:
            return False, "SID or service name is required"
        if not self.db_entry.username:
            return False, "Username is required"
        if not self.db_entry.password:
            return False, "Password is required"
        return True, None

    def _build_dsn(self) -> str:
        """Build Oracle connection DSN."""
        port = self.db_entry.port or 1521
        print(f"[ORACLE DB TEST] Build DSN - Host: {self.db_entry.host}, Port: {port}, SID/Service: {self.db_entry.oracle_sid_or_service}, Is_SID: {getattr(self.db_entry, 'oracle_is_sid', False)}")
        
        if getattr(self.db_entry, 'oracle_is_sid', False):
            try:
                import oracledb
                dsn_str = oracledb.makedsn(self.db_entry.host, port, sid=self.db_entry.oracle_sid_or_service)
                print(f"[ORACLE DB TEST] Using makedsn for SID. Result: {dsn_str}")
                return dsn_str
            except ImportError:
                # Fallback format if oracledb isn't loaded yet (though it should be)
                fallback_dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={self.db_entry.host})(PORT={port}))(CONNECT_DATA=(SID={self.db_entry.oracle_sid_or_service})))"
                print(f"[ORACLE DB TEST] Fallback DSN for SID: {fallback_dsn}")
                return fallback_dsn
                
        service_dsn = f"{self.db_entry.host}:{port}/{self.db_entry.oracle_sid_or_service}"
        print(f"[ORACLE DB TEST] Using simple connection string for Service: {service_dsn}")
        return service_dsn

    def get_connection_string(self) -> str:
        """Return DSN for Oracle."""
        return self._build_dsn()

    def connect(self) -> Any:
        """Establish Oracle connection."""
        import oracledb
        dsn = self._build_dsn()
        self.connection = oracledb.connect(
            dsn,
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

        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            columns = [desc[0].lower() for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        finally:
            cursor.close()

    def list_tables(self) -> List[TableDef]:
        """List all tables (Oracle)."""
        sql = """
            SELECT
                TABLE_NAME as name,
                OWNER as schema
            FROM ALL_TABLES
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_')
            ORDER BY OWNER, TABLE_NAME
        """
        results = self.execute_query(sql)
        return [TableDef(name=r['name'], schema=r['schema']) for r in results]

    def get_table_columns(self, table_name: str, schema: str = None) -> List[ColumnDef]:
        """Get columns for a table (Oracle)."""
        if not schema:
            schema = self.db_entry.username.upper()

        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                NULLABLE as is_nullable
            FROM ALL_TAB_COLUMNS
            WHERE TABLE_NAME = :table_name AND OWNER = :owner
            ORDER BY COLUMN_ID
        """
        results = self.execute_query(sql, {'table_name': table_name, 'owner': schema})
        return [
            ColumnDef(
                table_name=table_name,
                table_schema=schema,
                column_name=r['column_name'],
                data_type=r['data_type'],
                is_nullable=r['is_nullable'] == 'Y'
            )
            for r in results
        ]

    def list_procedures(self) -> List[ProcedureDef]:
        """List all procedures and functions (Oracle)."""
        sql = """
            SELECT
                OBJECT_NAME as name,
                OWNER as schema
            FROM ALL_PROCEDURES
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_')
            ORDER BY OWNER, OBJECT_NAME
        """
        results = self.execute_query(sql)
        return [ProcedureDef(name=r['name'], schema=r['schema']) for r in results]

    def list_views(self) -> List[ViewDef]:
        """List all views (Oracle)."""
        sql = """
            SELECT
                VIEW_NAME as name,
                OWNER as schema
            FROM ALL_VIEWS
            WHERE OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_')
            ORDER BY OWNER, VIEW_NAME
        """
        results = self.execute_query(sql)
        return [ViewDef(name=r['name'], schema=r['schema']) for r in results]

    def list_indexes(self) -> List[IndexDef]:
        """List all indexes (Oracle)."""
        sql = """
            SELECT
                INDEX_NAME as name,
                TABLE_NAME as table_name,
                TABLE_OWNER as table_schema,
                UNIQUENESS
            FROM ALL_INDEXES
            WHERE TABLE_OWNER NOT IN ('SYS', 'SYSTEM', 'XDB', 'APEX_')
            ORDER BY TABLE_NAME, INDEX_NAME
        """
        results = self.execute_query(sql)
        return [
            IndexDef(
                name=r['name'],
                table_name=r['table_name'],
                table_schema=r['table_schema'],
                columns=[],
                is_unique=r['UNIQUENESS'] == 'UNIQUE'
            )
            for r in results
        ]
