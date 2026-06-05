"""
DBAnalyser Configuration
========================
Pydantic-validated settings loaded from analysis_config.yaml.
Every value can be overridden with an environment variable:
  DBANALYSER_<SECTION>_<KEY>=value

Phase-1 additions
-----------------
* DatabaseEntry — one entry in the `databases:` list
* Settings.databases — list of registered SQL Server databases
* Settings.get_database(name) — look up a database by name
* Settings.source / Settings.scope — scanner-friendly accessors
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator


# ─── helpers ──────────────────────────────────────────────────────────────────

def _load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ─── DatabaseEntry (multi-DB registry) ────────────────────────────────────────

class DatabaseEntry(BaseModel):
    """One database registered for analysis (multi-DB support)."""
    name:                      str                   # friendly label, e.g. "LTFS_PROD"
    db_type:                   str            = "mssql"  # mssql | oracle | postgresql | mysql | snowflake
    environment:               str            = "development"
    host:                      str            = "localhost"
    port:                      Optional[int]  = None  # None = use db_type default
    database_name:             str            = ""
    connection_string:         str            = ""    # full DSN overrides host/port/db
    use_windows_auth:          bool           = False  # MSSQL only
    username:                  str            = ""
    password:                  str            = ""
    oracle_sid_or_service:     Optional[str]  = None  # Oracle SID or service name
    snowflake_warehouse:       Optional[str]  = None  # Snowflake warehouse
    snowflake_role:            Optional[str]  = None  # Snowflake role
    encryption_key_id:         Optional[int]  = None  # Future: for encrypted credentials
    description:               str            = ""
    owner_label:               str            = ""
    tags:                      List[str]      = []
    is_active:                 bool           = True

    @property
    def effective_connection_string(self) -> str:
        """Return connection string for this database (delegates to driver)."""
        from dbanalyser.db.driver_factory import get_driver
        try:
            driver = get_driver(self)
            return driver.get_connection_string()
        except Exception as e:
            # Fallback to raw connection_string if driver fails
            if self.connection_string:
                return self.connection_string
            # Legacy fallback for MSSQL
            if self.db_type.lower() == 'mssql':
                try:
                    import pyodbc
                    _drivers = pyodbc.drivers()
                    if "ODBC Driver 18 for SQL Server" in _drivers:
                        driver = "{ODBC Driver 18 for SQL Server}"
                    elif "ODBC Driver 17 for SQL Server" in _drivers:
                        driver = "{ODBC Driver 17 for SQL Server}"
                    else:
                        driver = "{SQL Server}"
                except Exception:
                    driver = "{ODBC Driver 17 for SQL Server}"
                port = self.port or 1433
                base = f"DRIVER={driver};SERVER={self.host},{port};DATABASE={self.database_name};"
                if self.use_windows_auth:
                    return base + "Trusted_Connection=yes;"
                return base + f"UID={self.username};PWD={self.password};"
            raise


# ─── SourceConfig ─────────────────────────────────────────────────────────────

class SourceConfig(BaseModel):
    """Primary data source — used by the scanner."""
    mode:              str       = "file"       # "file" | "live_db"
    file_path:         str       = r"D:\LTFS"
    file_extensions:   List[str] = [".sql", ".ddl"]
    recursive:         bool      = True
    connection_string: str       = ""

    # Legacy aliases so old YAML keys still work
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # source_mode → mode
            if "source_mode" in data and "mode" not in data:
                data["mode"] = data.pop("source_mode")
            # file_input_path → file_path
            if "file_input_path" in data and "file_path" not in data:
                data["file_path"] = data.pop("file_input_path")
        return data


# ─── ScopeConfig ─────────────────────────────────────────────────────────────

class ScopeConfig(BaseModel):
    object_types: List[str] = [
        "Stored Procedure", "Table", "View", "Function", "Trigger",
    ]
    schemas:         List[str] = []    # [] = all schemas
    exclude_schemas: List[str] = ["sys", "INFORMATION_SCHEMA"]
    include_patterns: List[str] = []
    exclude_patterns: List[str] = []
    exclude_system_objects: bool = True
    max_object_size_kb: int = 500

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # include_schemas → schemas
            if "include_schemas" in data and "schemas" not in data:
                data["schemas"] = data.pop("include_schemas")
        return data


# ─── Other config sections ────────────────────────────────────────────────────

class AnalysisCategoryConfig(BaseModel):
    performance:        bool = True
    security:           bool = True
    data_safety:        bool = True
    reliability:        bool = True
    maintainability:    bool = True
    best_practices:     bool = True
    parameter_sniffing: bool = True


class AnalysisConfig(BaseModel):
    categories:              AnalysisCategoryConfig = AnalysisCategoryConfig()
    enable_custom_rules:     bool = False
    custom_rules_path:       str  = ""
    enable_dependency:       bool = True
    orphan_detection:        bool = True
    orphan_confidence_level: str  = "relaxed"
    enable_unused_joins:     bool = True
    enable_col_mismatches:   bool = True
    enable_pk_check:         bool = True
    enable_datatype_opt:     bool = True
    enable_unused_columns:   bool = True


class SeverityConfig(BaseModel):
    min_severity_to_report: str = "low"


class PerformanceConfig(BaseModel):
    parallel_threads:       int  = 4
    max_objects_to_scan:    int  = 0
    timeout_per_object:     int  = 30
    memory_limit_mb:        int  = 2048
    enable_caching:         bool = True
    max_procedure_lines:    int  = 500
    max_nesting_depth:      int  = 4
    max_parameters:         int  = 15
    slow_query_threshold_ms:int  = 1000


class LiveDbConfig(BaseModel):
    enable_index_analysis:  bool = True
    enable_dmv_analysis:    bool = True
    enable_exec_plan:       bool = False
    top_n_slow_queries:     int  = 50
    top_n_missing_indexes:  int  = 50
    top_n_wait_stats:       int  = 30


class OutputConfig(BaseModel):
    directory:       str       = "./output"
    formats:         List[str] = ["excel", "html", "csv", "json"]
    include_snippets: bool     = True
    max_snippet_lines:int      = 20

    # Legacy key
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "output_directory" in data and "directory" not in data:
                data["directory"] = data.pop("output_directory")
        return data


class PostgresConfig(BaseModel):
    host:        str = "localhost"
    port:        int = 5432
    database:    str = "dbanalyser"
    user:        str = "postgres"
    password:    str = ""
    db_schema:   str = "public"    # renamed from 'schema' — avoids shadowing BaseModel.schema
    min_conn:    int = 1
    max_conn:    int = 5

    # Accept "username" → "user" and "schema" → "db_schema" as aliases
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "username" in data and "user" not in data:
                data["user"] = data.pop("username")
            if "schema" in data and "db_schema" not in data:
                data["db_schema"] = data.pop("schema")
        return data

    @property
    def dsn(self) -> str:
        return (f"postgresql://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}")


class VersioningConfig(BaseModel):
    enabled:           bool = True
    store_source_hash: bool = True
    detect_drift:      bool = True
    max_history_runs:  int  = 100


class RunModeConfig(BaseModel):
    parallel_workers: int  = 4
    environment:      str  = "development"
    log_level:        str  = "INFO"
    log_file:         str  = ""
    dry_run:          bool = False

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "parallel_threads" in data and "parallel_workers" not in data:
                data["parallel_workers"] = data.pop("parallel_threads")
        return data


class ApiConfig(BaseModel):
    """
    REST API server configuration.

    api_key  : If set, every request must carry  X-API-Key: <value>
               or the query parameter             ?api_key=<value>.
               Leave blank for open / local access (no auth).
    host     : Bind address passed to uvicorn (default: all interfaces).
    port     : TCP port for the API server.
    """
    api_key:  str = ""
    host:     str = "0.0.0.0"
    port:     int = 8000
    reload:   bool = False


class NotificationsConfig(BaseModel):
    """Webhook alert configuration for Slack and Microsoft Teams."""
    enabled:               bool      = False
    slack_webhook_url:     str       = ""
    teams_webhook_url:     str       = ""
    alert_on_severity:     List[str] = ["Critical", "High"]
    min_findings_to_alert: int       = 1
    include_summary:       bool      = True


class CustomRulesConfig(BaseModel):
    """YAML-driven custom rules — define patterns without writing Python."""
    enabled:     bool      = False
    rules_dir:   str       = "./custom_rules"
    rules_files: List[str] = []


class SchedulerConfig(BaseModel):
    """Scheduled scan engine settings."""
    enabled:            bool = False
    check_interval_sec: int  = 60


class UserEntry(BaseModel):
    """One user entry under auth.users (for JWT auth)."""
    username:      str
    password_hash: str       # bcrypt hash — generate with dbanalyser auth hash-password
    role:          str = "viewer"   # viewer | analyst | admin


class AuthConfig(BaseModel):
    """
    JWT authentication for the REST API.

    Set auth.enabled = true and populate auth.users to require Bearer tokens.
    Generate a user entry with:  dbanalyser auth hash-password
    """
    enabled:              bool           = False
    secret_key:           str            = "change-me-in-production"
    algorithm:            str            = "HS256"
    token_expire_minutes: int            = 480
    users:                List[UserEntry] = []


class AIOptimizerConfig(BaseModel):
    """
    AI SQL Optimizer — Ollama settings.
    """
    enabled:                bool  = False
    api_key:                str   = ""
    model:                  str   = "llama3:8b-instruct-q4_K_M"
    max_tokens:             int   = 4096
    temperature:            float = 0.1
    include_schema:         bool  = True
    include_execution_plan: bool  = True
    persist_results:        bool  = True


class ComplianceConfig(BaseModel):
    """
    Compliance rule packs configuration.

    enabled_packs : list of pack names to activate.
        Supported values: "sox" | "gdpr" | "rbi"
        Leave empty to run no compliance checks (default).
    """
    enabled_packs: List[str] = []

    # SOX-specific overrides
    financial_schemas: List[str] = ["dbo"]
    audit_tables:      List[str] = []          # tables that already hold audit rows

    # GDPR-specific overrides
    pii_column_patterns: List[str] = [
        "email", "phone", "ssn", "nric", "dob", "passport",
        "address", "mobile", "credit_card",
    ]

    # RBI-specific overrides
    financial_tables: List[str] = []           # additional sensitive table names
    require_rls:      bool       = False        # raise finding if RLS policy absent


# ─── Main Settings ────────────────────────────────────────────────────────────

class Settings(BaseModel):
    """
    Full DBAnalyser configuration.
    Loaded from YAML; individual fields overrideable via env vars.
    """
    source:      SourceConfig      = SourceConfig()
    scope:       ScopeConfig       = ScopeConfig()
    analysis:    AnalysisConfig    = AnalysisConfig()
    severity:    SeverityConfig    = SeverityConfig()
    performance: PerformanceConfig = PerformanceConfig()
    live_db:     LiveDbConfig      = LiveDbConfig()
    output:      OutputConfig      = OutputConfig()
    postgres:    PostgresConfig    = PostgresConfig()
    versioning:  VersioningConfig  = VersioningConfig()
    run:         RunModeConfig     = RunModeConfig()
    compliance:    ComplianceConfig    = ComplianceConfig()
    api:           ApiConfig          = ApiConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    custom_rules:  CustomRulesConfig   = CustomRulesConfig()
    scheduler:     SchedulerConfig     = SchedulerConfig()
    auth:          AuthConfig          = AuthConfig()
    ai_optimizer:  AIOptimizerConfig   = AIOptimizerConfig()

    # ── Multi-DB registry ────────────────────────────────────────────────────
    databases: List[DatabaseEntry] = []

    # ── Runtime fields (auto-generated) ─────────────────────────────────────
    run_id:    str = ""
    timestamp: str = ""

    @model_validator(mode="after")
    def _set_runtime_fields(self) -> "Settings":
        if not self.run_id:
            self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not self.timestamp:
            self.timestamp = self.run_id
        return self

    # ── Convenience ─────────────────────────────────────────────────────────

    @property
    def output_dir(self) -> Path:
        p = Path(self.output.directory)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def category_enabled(self, category: str) -> bool:
        cat = category.lower().replace(" ", "_").replace("-", "_")
        return getattr(self.analysis.categories, cat, True)

    def object_in_scope(self, name: str, obj_type: str, schema: str = "dbo") -> bool:
        import fnmatch
        if self.scope.schemas and schema not in self.scope.schemas:
            return False
        if schema in self.scope.exclude_schemas:
            return False
        if obj_type not in self.scope.object_types:
            return False
        for pat in self.scope.exclude_patterns:
            if fnmatch.fnmatch(name, pat):
                return False
        if self.scope.include_patterns:
            return any(fnmatch.fnmatch(name, p) for p in self.scope.include_patterns)
        return True

    def get_database(self, name: str) -> Optional[DatabaseEntry]:
        """Look up a registered database entry by name (case-insensitive)."""
        nl = name.lower()
        for db in self.databases:
            if db.name.lower() == nl:
                return db
        return None

    def get_active_databases(self) -> List[DatabaseEntry]:
        return [db for db in self.databases if db.is_active]

    def settings_for_database(self, db: DatabaseEntry) -> "Settings":
        """
        Return a copy of this Settings with source patched for the given database.
        Used by multi-DB run loops.
        """
        patched = self.model_copy(deep=True)
        patched.source.mode = "live_db"
        patched.source.connection_string = db.effective_connection_string
        return patched

    def summary(self) -> dict:
        return {
            "run_id":      self.run_id,
            "source_mode": self.source.mode,
            "environment": self.run.environment,
            "dry_run":     self.run.dry_run,
            "threads":     self.run.parallel_workers,
            "output_dir":  str(self.output_dir),
            "databases":   [db.name for db in self.get_active_databases()],
        }


# ─── Loader ───────────────────────────────────────────────────────────────────

def load_config(path: str | Path = "analysis_config.yaml") -> Settings:
    """
    Load Settings from a YAML file.
    Env-var overrides: DBANALYSER_<SECTION>_<KEY>=value
    e.g.  DBANALYSER_POSTGRES_PASSWORD=secret
          DBANALYSER_SOURCE_MODE=live_db
    """
    raw = _load_yaml(path)

    # Load local overrides if they exist
    local_path = Path(path).parent / "analysis_config_local.yaml"
    if local_path.exists():
        local_raw = _load_yaml(local_path)
        # Deep merge local_raw into raw
        def deep_merge(dict1, dict2):
            for k, v in dict2.items():
                if k in dict1 and isinstance(dict1[k], dict) and isinstance(v, dict):
                    deep_merge(dict1[k], v)
                else:
                    dict1[k] = v
        deep_merge(raw, local_raw)


    # Top-level YAML key aliases (old → new)
    _top_aliases = {
        "data_source": "source",
        "run_mode":    "run",
    }
    for old, new in _top_aliases.items():
        if old in raw and new not in raw:
            raw[new] = raw.pop(old)

    # Env-var overrides: DBANALYSER_POSTGRES_PASSWORD → raw["postgres"]["password"]
    prefix = "DBANALYSER_"
    for key, val in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("_", 1)
        if len(parts) == 2:
            section, field = parts
            if section in raw and isinstance(raw[section], dict):
                raw[section][field] = val
            else:
                raw.setdefault(section, {})[field] = val

    return Settings(**raw)
