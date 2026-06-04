"""
DBAnalyser — Python dataclasses mirroring the PostgreSQL schema.
These are plain dataclasses (no ORM) — passed between engine and repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional


# ─── DbRegistry ──────────────────────────────────────────────────────────────

@dataclass
class DbRegistry:
    """A registered database being monitored (multi-DB support)."""
    name:                      str
    db_type:                   str            = "mssql"
    environment:               str            = "development"
    host:                      str            = "localhost"
    port:                      Optional[int]  = None
    database_name:             str            = ""
    connection_string:         Optional[str]  = None
    use_windows_auth:          bool           = False
    username:                  Optional[str]  = None
    password:                  Optional[str]  = None
    oracle_sid_or_service:     Optional[str]  = None
    snowflake_warehouse:       Optional[str]  = None
    snowflake_role:            Optional[str]  = None
    encryption_key_id:         Optional[int]  = None
    description:               Optional[str]  = None
    owner_label:               Optional[str]  = None
    tags:                      List[str]      = field(default_factory=list)
    is_active:                 bool           = True
    # populated after DB insert
    id:                        Optional[int]  = None


# ─── Run ─────────────────────────────────────────────────────────────────────

@dataclass
class Run:
    run_id:          str
    label:           str             = ""
    db_registry_id:  Optional[int]   = None      # FK → db_registry.id
    timestamp:       Optional[datetime] = None
    environment:     str             = "development"
    source_mode:     str             = "file"
    config_hash:     Optional[str]   = None
    file_input_path: Optional[str]   = None
    database_name:   Optional[str]   = None
    host:            Optional[str]   = None
    duration_sec:    Optional[float] = None
    total_objects:   int             = 0
    total_issues:    int             = 0
    critical_count:  int             = 0
    high_count:      int             = 0
    medium_count:    int             = 0
    low_count:       int             = 0
    health_score:    Optional[float] = None
    status:          str             = "success"
    notes:           Optional[str]   = None
    # populated after DB insert
    id:              Optional[int]   = None


# ─── ObjectSnapshot ──────────────────────────────────────────────────────────

@dataclass
class ObjectSnapshot:
    run_id:        int              # FK → runs.id  (integer, not UUID)
    object_name:   str
    object_type:   str
    schema_name:   str             = "dbo"
    file_path:     Optional[str]   = None
    content_hash:  Optional[str]   = None
    lines:         Optional[int]   = None
    size_kb:       Optional[float] = None
    risk_score:    float           = 0.0
    risk_level:    str             = "MINIMAL"
    issue_count:   int             = 0
    critical_count:int             = 0
    high_count:    int             = 0
    source:        str             = "file"
    content_drift: bool            = False


# ─── Finding ─────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    run_id:         int             # FK → runs.id  (integer)
    object_name:    str
    category:       str
    issue:          str
    severity:       str             # Critical | High | Medium | Low
    object_type:    str             = ""
    schema_name:    str             = "dbo"
    line_number:    Optional[int]   = None
    recommendation: Optional[str]  = None
    snippet:        Optional[str]  = None
    rule_id:        Optional[str]  = None
    status:         str            = "Open"
    first_seen_run: Optional[int]  = None
    last_seen_run:  Optional[int]  = None
    is_new:         bool           = True
    is_regression:  bool           = False
    jira_ticket:    Optional[str]  = None
    notes:          Optional[str]  = None


# ─── DmvSnapshot ─────────────────────────────────────────────────────────────

@dataclass
class DmvSnapshot:
    run_id:    int              # FK → runs.id  (integer)
    dmv_type:  str
    data_json: List[Dict[str, Any]]
    row_count: int = 0


# ─── HealthTrend ─────────────────────────────────────────────────────────────

@dataclass
class HealthTrend:
    run_id:          int             # FK → runs.id
    db_registry_id:  Optional[int]  = None
    db_name:         str            = ""
    environment:     str            = "development"
    timestamp:       Optional[datetime] = None
    health_score:    Optional[float]= None
    total_objects:   int            = 0
    total_issues:    int            = 0
    critical_count:  int            = 0
    high_count:      int            = 0
    medium_count:    int            = 0
    low_count:       int            = 0
    new_issues:      int            = 0
    resolved_issues: int            = 0


# ─── helpers ─────────────────────────────────────────────────────────────────

SEV_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def severity_rank(sev: str) -> int:
    return SEV_ORDER.get(sev, 0)


def health_score(
    critical: int, high: int, medium: int, low: int,
    total_objects: int = 0, orphans: int = 0, no_pk: int = 0,
) -> float:
    """Composite health score 0–100. Higher = healthier."""
    score = 100.0
    score -= critical * 5
    score -= high     * 2
    score -= medium   * 0.5
    score -= low      * 0.1
    score -= orphans  * 0.3
    score -= no_pk    * 1.0
    return round(max(0.0, min(100.0, score)), 1)


# =============================================================================
# Phase G — Multi-Tenancy models
# =============================================================================

@dataclass
class Organization:
    name:      str
    slug:      str
    plan:      str           = "free"
    is_active: bool          = True
    id:        Optional[int] = None


@dataclass
class User:
    org_id:        int
    username:      str
    email:         str
    password_hash: str
    role:          str                = "viewer"
    is_active:     bool               = True
    last_login_at: Optional[datetime] = None
    id:            Optional[int]      = None


@dataclass
class AssessmentConfig:
    org_id:         int
    db_registry_id: int
    config_json:    Dict[str, Any] = field(default_factory=dict)
    id:             Optional[int]  = None


@dataclass
class Invitation:
    org_id:      int
    email:       str
    role:        str
    token:       str
    expires_at:  datetime
    accepted_at: Optional[datetime] = None
    id:          Optional[int]      = None
