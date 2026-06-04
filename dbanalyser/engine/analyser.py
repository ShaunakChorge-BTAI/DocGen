"""
Analyser — orchestrates the rule engine and extended schema checks.

Responsibilities
----------------
1. Load SQL objects via scanner.load_objects()
2. Run all applicable rules from the rule registry (concurrent)
3. Run extended schema checks (unused JOINs, col type mismatches, PK check, etc.)
4. Return a structured AnalysisResult
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .rules      import ALL_RULES, BaseRule, RuleFinding, SQLObject, build_rule_set
from .scanner    import load_objects

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ObjectResult:
    obj:      SQLObject
    findings: List[RuleFinding] = field(default_factory=list)
    db_name:  str = ""            # populated for multi-DB runs

    @property
    def severity_counts(self) -> Dict[str, int]:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    @property
    def health_score(self) -> float:
        c = self.severity_counts
        # Low findings are cosmetic/style issues; use small weight so bulk
        # best-practice violations don't crush the score to zero.
        score = 100 - c["Critical"]*5 - c["High"]*2 - c["Medium"]*0.5 - c["Low"]*0.02
        return max(0.0, round(score, 1))


@dataclass
class AnalysisResult:
    run_label:      str
    source_mode:    str
    db_name:        str = ""          # populated for multi-DB runs
    db_registry_id: int = 0           # FK back to db_registry.id (0 = unset)
    object_results: List[ObjectResult] = field(default_factory=list)
    extended:       Dict[str, pd.DataFrame] = field(default_factory=dict)
    elapsed_sec:    float = 0.0

    # ── aggregate helpers ────────────────────────────────────────────────────

    @property
    def total_objects(self) -> int:
        return len(self.object_results)

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.object_results)

    @property
    def severity_counts(self) -> Dict[str, int]:
        totals: Dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for r in self.object_results:
            for sev, cnt in r.severity_counts.items():
                totals[sev] = totals.get(sev, 0) + cnt
        return totals

    @property
    def overall_health(self) -> float:
        if not self.object_results:
            return 100.0
        c = self.severity_counts
        # Low findings are cosmetic/style issues; use small weight so bulk
        # best-practice violations don't crush the score to zero.
        score = 100 - c["Critical"]*5 - c["High"]*2 - c["Medium"]*0.5 - c["Low"]*0.02
        return max(0.0, round(score, 1))

    def all_findings_df(self) -> pd.DataFrame:
        rows = []
        for or_ in self.object_results:
            for f in or_.findings:
                rows.append({
                    "rule_id":        f.rule_id,
                    "category":       f.category,
                    "severity":       f.severity,
                    "object_name":    f"{or_.obj.schema}.{or_.obj.name}",
                    "object_type":    or_.obj.obj_type,
                    "db_name":        self.db_name,
                    "line_number":    f.line_number,
                    "issue":          f.issue,
                    "recommendation": f.recommendation,
                    "snippet":        f.snippet,
                })
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Rule runner
# ---------------------------------------------------------------------------

def _run_rules_for_object(
        obj: SQLObject,
        rules: List[BaseRule],
        enabled_categories: Optional[List[str]] = None,
) -> ObjectResult:
    """Run all enabled rules against a single SQLObject."""
    findings: List[RuleFinding] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if enabled_categories and rule.category not in enabled_categories:
            continue
        try:
            findings.extend(rule.analyse(obj))
        except Exception as exc:
            logger.debug("Rule %s failed on %s.%s: %s",
                         rule.rule_id, obj.schema, obj.name, exc)
    return ObjectResult(obj=obj, findings=findings)


# ---------------------------------------------------------------------------
# Extended schema checks (pure-Python / pandas)
# ---------------------------------------------------------------------------

def _check_tables_without_pk(objects: List[SQLObject]) -> pd.DataFrame:
    """
    Flag Table objects whose source contains no PRIMARY KEY definition.
    (Works on file-based DDL; for live-DB a sys.key_constraints query is better.)
    """
    rows = []
    import re
    for obj in objects:
        if obj.obj_type != "Table":
            continue
        has_pk = bool(re.search(r'\bPRIMARY\s+KEY\b', obj.source, re.IGNORECASE))
        if not has_pk:
            rows.append({
                "schema_name": obj.schema,
                "table_name":  obj.name,
                "file_path":   obj.file_path,
                "issue":       "No PRIMARY KEY constraint defined",
            })
    return pd.DataFrame(rows)


def _check_duplicate_indexes(objects: List[SQLObject]) -> pd.DataFrame:
    """
    Detect CREATE INDEX statements that share the same leading key column on the same table.
    Very coarse heuristic — relies on DDL being available in source.
    """
    import re
    from collections import defaultdict

    index_map: Dict[str, list] = defaultdict(list)
    for obj in objects:
        if obj.obj_type != "Table":
            continue
        for m in re.finditer(
                r'\bCREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+|CLUSTERED\s+)?INDEX\s+'
                r'(\[?\w+\]?)\s+ON\s+\[?\w+\]?\.\[?\w+\]?\s*\(([^)]+)\)',
                obj.source, re.IGNORECASE):
            idx_name   = m.group(1).strip("[]")
            key_cols   = m.group(2).strip()
            first_col  = key_cols.split(",")[0].strip().strip("[]").split()[0]
            table_key  = f"{obj.schema}.{obj.name}"
            index_map[(table_key, first_col.upper())].append(idx_name)

    rows = []
    for (table, col), idx_names in index_map.items():
        if len(idx_names) > 1:
            rows.append({
                "table":          table,
                "leading_column": col,
                "indexes":        ", ".join(idx_names),
                "issue":          "Multiple indexes share the same leading column",
            })
    return pd.DataFrame(rows)


def _check_column_type_mismatches(objects: List[SQLObject]) -> pd.DataFrame:
    """
    Scan JOIN … ON clauses for columns that appear with different type casts
    across multiple files — very approximate without a full schema graph.
    """
    # This is intentionally lightweight; the notebook version has richer metadata.
    import re
    from collections import defaultdict

    col_types: Dict[str, set] = defaultdict(set)
    for obj in objects:
        # Simple CREATE TABLE column extraction
        for m in re.finditer(
                r'^\s*\[?(\w+)\]?\s+((?:N?VAR)?CHAR|INT|BIGINT|DECIMAL|NUMERIC|'
                r'DATE(?:TIME)?|BIT|FLOAT|MONEY|UNIQUEIDENTIFIER)\b',
                obj.source, re.IGNORECASE | re.MULTILINE):
            col_types[m.group(1).upper()].add(m.group(2).upper())

    rows = []
    for col, types in col_types.items():
        if len(types) > 1:
            rows.append({
                "column_name": col,
                "types_found": ", ".join(sorted(types)),
                "issue":       "Same column name used with different data types across tables",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_analysis(
        cfg,
        rules:           Optional[List[BaseRule]] = None,
        max_workers:     int = 4,
        run_label:       str = "",
        db_name:         str = "",
        db_registry_id:  int = 0,
) -> AnalysisResult:
    """
    Run the full analysis pipeline.

    Parameters
    ----------
    cfg            : Settings instance
    rules          : override the default ALL_RULES list
    max_workers    : thread-pool size for parallel rule execution
    run_label      : human-readable label for this run (e.g., a timestamp)
    db_name        : friendly name of the database being scanned (multi-DB)
    db_registry_id : FK to db_registry.id (0 = not persisted / file-mode)
    """
    t0 = time.perf_counter()

    # Use caller-supplied rules, or build from config (respects compliance packs),
    # or fall back to the base ALL_RULES list.
    if rules is not None:
        effective_rules = rules
    else:
        try:
            effective_rules = build_rule_set(cfg)
        except Exception:
            effective_rules = ALL_RULES

    # ── 1. Load objects ──────────────────────────────────────────────────────
    logger.info("Loading SQL objects (mode=%s) …", cfg.source.mode)
    objects: List[SQLObject] = list(load_objects(cfg))
    logger.info("Loaded %d objects", len(objects))

    # ── 2. Determine enabled categories ─────────────────────────────────────
    enabled_categories: Optional[List[str]] = None
    if hasattr(cfg, "categories") and cfg.categories:
        enabled_categories = [
            cat for cat, enabled in cfg.categories.__dict__.items() if enabled
        ]

    # ── 3. Run rules in parallel ─────────────────────────────────────────────
    object_results: List[ObjectResult] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_rules_for_object, obj, effective_rules, enabled_categories): obj
            for obj in objects
        }
        for future in as_completed(futures):
            try:
                object_results.append(future.result())
            except Exception as exc:
                obj = futures[future]
                logger.warning("Analysis failed for %s.%s: %s", obj.schema, obj.name, exc)

    # Sort by health score ascending (worst first)
    object_results.sort(key=lambda r: r.health_score)

    # ── 4. Extended checks ───────────────────────────────────────────────────
    extended: Dict[str, pd.DataFrame] = {}
    try:
        extended["tables_without_pk"]      = _check_tables_without_pk(objects)
        extended["duplicate_indexes"]      = _check_duplicate_indexes(objects)
        extended["column_type_mismatches"] = _check_column_type_mismatches(objects)
    except Exception as exc:
        logger.warning("Extended checks partially failed: %s", exc)

    elapsed = round(time.perf_counter() - t0, 2)

    result = AnalysisResult(
        run_label      = run_label or time.strftime("%Y%m%d_%H%M%S"),
        source_mode    = cfg.source.mode,
        db_name        = db_name,
        db_registry_id = db_registry_id,
        object_results = object_results,
        extended       = extended,
        elapsed_sec    = elapsed,
    )

    logger.info(
        "Analysis complete in %.1fs | objects=%d | findings=%d | health=%.1f",
        elapsed, result.total_objects, result.total_findings, result.overall_health,
    )
    return result
