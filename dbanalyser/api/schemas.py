"""
DBAnalyser REST API — Pydantic request / response schemas.
All API responses are typed here so FastAPI auto-generates OpenAPI docs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Generic ──────────────────────────────────────────────────────────────────

class OkResponse(BaseModel):
    ok:      bool    = True
    message: str     = "success"


class ErrorResponse(BaseModel):
    ok:      bool = False
    detail:  str


# ─── Database Registry ────────────────────────────────────────────────────────

class DbRegistryCreate(BaseModel):
    id:                        Optional[int] = None  # For editing existing databases
    name:                      str
    db_type:                   str  = "mssql"
                               # mssql | oracle | postgresql | mysql | snowflake
    environment:               str  = "development"
    host:                      str  = "localhost"
    port:                      Optional[int] = None
                               # None = use db_type default
    database_name:             str  = ""
    connection_string:         Optional[str] = None
    use_windows_auth:          bool = False  # MSSQL only
    username:                  Optional[str] = None
    password:                  Optional[str] = None   # SQL Auth password; omitted from responses
    oracle_sid_or_service:     Optional[str] = None  # Oracle only
    oracle_is_sid:             bool = False          # Oracle only
    snowflake_warehouse:       Optional[str] = None  # Snowflake only
    snowflake_role:            Optional[str] = None  # Snowflake only
    description:               Optional[str] = None
    owner_label:               Optional[str] = None
    tags:                      List[str]     = []
    is_active:                 bool = True


class DbRegistryResponse(BaseModel):
    id:                        int
    name:                      str
    db_type:                   str
    environment:               str
    host:                      str
    port:                      Optional[int]
    database_name:             str
    connection_string:         Optional[str] = None
    use_windows_auth:          bool
    username:                  Optional[str] = None
    # password intentionally omitted from responses
    oracle_sid_or_service:     Optional[str] = None
    oracle_is_sid:             bool = False
    snowflake_warehouse:       Optional[str] = None
    snowflake_role:            Optional[str] = None
    description:               Optional[str] = None
    owner_label:               Optional[str] = None
    tags:                      List[str]     = []
    is_active:                 bool
    last_run_at:               Optional[datetime] = None
    last_health:               Optional[float]    = None
    created_at:                Optional[datetime] = None
    updated_at:                Optional[datetime] = None


# ─── Runs ─────────────────────────────────────────────────────────────────────

class RunTriggerRequest(BaseModel):
    db_name:    Optional[str]  = None   # named DB from registry; None = file mode
    all_dbs:    bool           = False
    label:      str            = ""
    run_dmv:    bool           = False
    formats:    List[str]      = ["json"]
    no_persist: bool           = False


class RunResponse(BaseModel):
    id:             int
    run_id:         str
    label:          str
    db_name:        Optional[str]  = None
    environment:    Optional[str]  = None
    source_mode:    str
    health_score:   Optional[float]= None
    total_objects:  int
    total_issues:   int
    critical_count: int
    high_count:     int
    medium_count:   int
    low_count:      int
    status:         str
    timestamp:      Optional[datetime] = None
    duration_sec:   Optional[float]    = None


class RunListResponse(BaseModel):
    runs:  List[RunResponse]
    total: int


# ─── Findings ─────────────────────────────────────────────────────────────────

class FindingResponse(BaseModel):
    id:             int
    run_id:         int
    rule_id:        Optional[str]  = None
    category:       str
    severity:       str
    object_name:    str
    object_type:    str
    schema_name:    str
    issue:          str
    recommendation: Optional[str]  = None
    line_number:    Optional[int]  = None
    snippet:        Optional[str]  = None
    status:         str
    is_new:         bool
    is_regression:  bool
    created_at:     Optional[datetime] = None


class FindingListResponse(BaseModel):
    findings: List[FindingResponse]
    total:    int
    run_id:   int


class FindingStatusUpdate(BaseModel):
    status: str   = Field(..., pattern="^(open|acknowledged|fixed|suppressed|wontfix)$")
    reason: Optional[str] = None
    jira:   Optional[str] = None


# ─── Trend ────────────────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    timestamp:      datetime
    health_score:   Optional[float]
    total_issues:   int
    critical_count: int
    high_count:     int
    medium_count:   int
    low_count:      int
    new_issues:     int
    resolved_issues:int
    db_name:        Optional[str] = None


class TrendResponse(BaseModel):
    db_name: Optional[str]
    points:  List[TrendPoint]


# ─── Estate Summary ───────────────────────────────────────────────────────────

class DbSummaryItem(BaseModel):
    id:             int
    name:           str
    environment:    str
    owner_label:    Optional[str]
    health_score:   Optional[float]
    critical_count: Optional[int]
    high_count:     Optional[int]
    total_issues:   Optional[int]
    total_objects:  Optional[int]
    last_run_ts:    Optional[datetime]
    is_active:      bool


class EstateSummaryResponse(BaseModel):
    total_databases:  int
    avg_health:       Optional[float]
    total_findings:   int
    total_critical:   int
    databases:        List[DbSummaryItem]


# ─── Analysis job (async trigger) ────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id:  str
    status:  str          # queued | running | done | failed
    message: str = ""
    run_id:  Optional[int] = None
    progress_percent: int = 0          # 0-100%
    objects_analyzed: Optional[int] = None
    total_objects: Optional[int] = None


# ─── Health gate (CI/CD quality gate) ────────────────────────────────────────

class PackGateResult(BaseModel):
    pack:      str
    count:     int
    threshold: int
    passed:    bool


class HealthGateResponse(BaseModel):
    run_id:       int
    passed:       bool
    health_score: Optional[float]
    checks:       List[PackGateResult]
    message:      str


# ─── Scheduled tasks ─────────────────────────────────────────────────────────

class ScheduledTaskCreate(BaseModel):
    db_name:  str
    schedule: str = "manual"    # hourly | daily@HH:MM | weekly@DAY@HH:MM | manual
    label:    str = ""
    enabled:  bool = True
    run_dmv:  bool = False
    formats:  List[str] = ["json"]


class ScheduledTaskResponse(ScheduledTaskCreate):
    id:        int
    last_run:  Optional[datetime] = None
    next_run:  Optional[datetime] = None
    created_at:Optional[datetime] = None


# ─── Schema Intelligence ──────────────────────────────────────────────────────

class SchemaObjectResponse(BaseModel):
    id:             int
    db_registry_id: Optional[int]  = None
    object_type:    str
    schema_name:    str
    object_name:    str
    parent_name:    str            = ""
    data_type:      Optional[str]  = None
    is_nullable:    Optional[bool] = None
    is_primary_key: bool           = False
    is_foreign_key: bool           = False
    definition:     Optional[str]  = None
    ingested_at:    Optional[datetime] = None


class SchemaObjectListResponse(BaseModel):
    objects: List[SchemaObjectResponse]
    total:   int


class SchemaSearchRequest(BaseModel):
    query:        str
    top_k:        int           = Field(10, ge=1, le=100)
    min_score:    float         = Field(0.0, ge=0.0, le=1.0)
    object_types: List[str]     = []
    db_registry_id: Optional[int] = None


class SchemaSearchResult(BaseModel):
    object_type:    str
    schema_name:    str
    object_name:    str
    parent_name:    str
    definition:     Optional[str]  = None
    similarity_score: float


class SchemaSearchResponse(BaseModel):
    query:   str
    results: List[SchemaSearchResult]
    total:   int


# =============================================================================
# Phase G — Multi-Tenancy schemas
# =============================================================================

# ─── Organizations ────────────────────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    name: str
    plan: str = "free"


class OrganizationResponse(BaseModel):
    id:         int
    name:       str
    slug:       str
    plan:       str
    is_active:  bool
    created_at: Optional[datetime] = None


class OrganizationStats(BaseModel):
    id:          int
    name:        str
    slug:        str
    plan:        str
    user_count:  int = 0
    db_count:    int = 0
    run_count:   int = 0
    last_run_at: Optional[datetime] = None
    is_active:   bool


# ─── Users ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email:    str
    password: str
    role:     str = "viewer"


class UserResponse(BaseModel):
    id:            int
    org_id:        int
    username:      str
    email:         str
    role:          str
    is_active:     bool
    last_login_at: Optional[datetime] = None
    created_at:    Optional[datetime] = None


class UserRoleUpdate(BaseModel):
    role: str   # viewer | analyst | admin


# ─── Invitations ──────────────────────────────────────────────────────────────

class InvitationResponse(BaseModel):
    id:          int
    org_id:      int
    email:       str
    role:        str
    expires_at:  datetime
    accepted_at: Optional[datetime] = None
    created_at:  Optional[datetime] = None


# ─── Assessment Configs ───────────────────────────────────────────────────────

class AssessmentConfigCreate(BaseModel):
    db_registry_id: int
    config_json:    Dict[str, Any] = {}


class AssessmentConfigResponse(AssessmentConfigCreate):
    id:         int
    org_id:     int
    db_name:    Optional[str]      = None
    environment:Optional[str]      = None
    updated_at: Optional[datetime] = None


# ─── Platform stats (super-admin) ────────────────────────────────────────────

class PlatformStatsResponse(BaseModel):
    orgs:     int
    users:    int
    databases:int
    total_runs: int
    runs_30d:   int


class SchemaSummaryResponse(BaseModel):
    db_registry_id: Optional[int]
    counts:         Dict[str, Any]
    total:          int


# ─── AI Optimizer ─────────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    object_name:     str
    sql:             str
    schema_context:  Optional[str] = None
    execution_plan:  Optional[str] = None
    findings:        List[Dict[str, Any]] = []
    model:           Optional[str] = None
    api_key:         Optional[str] = None
    persist:         bool = True
    mode:            str = "quick"  # "quick" (Ollama) or "advanced" (deprecated)


class OptimizationChangeItem(BaseModel):
    type:   str
    before: str
    after:  str
    impact: str


class OptimizeResponse(BaseModel):
    object_name:      str
    optimized_sql:    Optional[str]  = None
    reasoning:        str            = ""
    changes:          List[OptimizationChangeItem] = []
    confidence_score: float          = 0.0
    no_change_needed: bool           = False
    no_change_reason: str            = ""
    tokens_used:      int            = 0
    model_used:       str            = ""
    error:            Optional[str]  = None


class AiOptimizationResponse(BaseModel):
    id:                   int
    run_id:               Optional[int]  = None
    db_registry_id:       Optional[int]  = None
    object_name:          str
    original_sql:         Optional[str]  = None
    optimized_sql:        Optional[str]  = None
    reasoning:            Optional[str]  = None
    confidence_score:     float          = 0.0
    model_used:           str            = ""
    tokens_used:          int            = 0
    created_at:           Optional[datetime] = None


class AiOptimizationListResponse(BaseModel):
    optimizations: List[AiOptimizationResponse]
    total:         int


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id:            int
    username:      str
    action:        str
    resource_type: str            = ""
    resource_id:   str            = ""
    details:       Dict[str, Any] = {}
    ip_address:    str            = ""
    created_at:    Optional[datetime] = None


class AuditLogListResponse(BaseModel):
    logs:   List[AuditLogResponse]
    total:  int
    limit:  int
    offset: int


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineStepResponse(BaseModel):
    id:           int
    run_id:       int
    step:         str
    status:       str
    started_at:   Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_sec: Optional[float]    = None
    error:        Optional[str]      = None
    details:      Dict[str, Any]     = {}


class PipelineResponse(BaseModel):
    run_id: int
    steps:  List[PipelineStepResponse]
    total:  int
