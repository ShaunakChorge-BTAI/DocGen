"""JSON report generator — machine-readable structured output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_json(
        result,
        output_path: str,
        dmv_results: Optional[dict] = None,
        indent: int = 2,
) -> str:
    """
    Write a structured JSON report.  Returns the output file path.

    The top-level structure is:
    {
      "meta":    { run_label, source_mode, elapsed_sec, generated_at },
      "summary": { overall_health, total_objects, total_findings, severity_counts },
      "findings": [ { rule_id, category, severity, object_name, ... }, … ],
      "object_health": [ { object, type, health_score, ... }, … ],
      "extended": { tables_without_pk: [...], ... },
      "dmv":      { dmv_index_usage: [...], ... }  // optional
    }
    """
    import time

    sev = result.severity_counts

    doc = {
        "meta": {
            "run_label":    result.run_label,
            "source_mode":  result.source_mode,
            "elapsed_sec":  result.elapsed_sec,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "summary": {
            "overall_health":  result.overall_health,
            "total_objects":   result.total_objects,
            "total_findings":  result.total_findings,
            "severity_counts": sev,
        },
        "findings": [],
        "object_health": [],
        "extended": {},
    }

    # Findings
    all_df = result.all_findings_df()
    if not all_df.empty:
        doc["findings"] = all_df.fillna("").to_dict(orient="records")

    # Object health
    doc["object_health"] = [
        {
            "object":        f"{r.obj.schema}.{r.obj.name}",
            "type":          r.obj.obj_type,
            "schema":        r.obj.schema,
            "name":          r.obj.name,
            "lines":         r.obj.lines,
            "health_score":  r.health_score,
            "critical":      r.severity_counts.get("Critical", 0),
            "high":          r.severity_counts.get("High", 0),
            "medium":        r.severity_counts.get("Medium", 0),
            "low":           r.severity_counts.get("Low", 0),
            "total_findings":len(r.findings),
        }
        for r in result.object_results
    ]

    # Extended
    for key in ("tables_without_pk", "duplicate_indexes", "column_type_mismatches"):
        df = result.extended.get(key)
        if df is not None and not df.empty:
            doc["extended"][key] = df.fillna("").to_dict(orient="records")
        else:
            doc["extended"][key] = []

    # DMV (convert DataFrames to list of dicts)
    if dmv_results:
        doc["dmv"] = {}
        for key, df in dmv_results.items():
            try:
                if df is not None and not df.empty:
                    doc["dmv"][key] = df.fillna("").to_dict(orient="records")
                else:
                    doc["dmv"][key] = []
            except Exception:
                doc["dmv"][key] = []

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=indent, default=str), encoding="utf-8")
    logger.info("JSON report written to %s", path)
    return str(path)
