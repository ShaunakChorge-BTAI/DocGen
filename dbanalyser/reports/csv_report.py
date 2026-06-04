"""CSV report generator — writes one CSV per category + a master findings CSV."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def generate_csv(
        result,
        output_dir: str,
        dmv_results: Optional[dict] = None,
) -> list[str]:
    """
    Write CSV files to *output_dir*.

    Returns a list of written file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    all_df = result.all_findings_df()

    # Master findings
    if not all_df.empty:
        path = out / "findings_all.csv"
        all_df.to_csv(path, index=False)
        written.append(str(path))
        logger.info("Wrote %s (%d rows)", path.name, len(all_df))

        # Per-category
        for cat in sorted(all_df["category"].unique()):
            safe_name = cat.lower().replace(" ", "_").replace("/", "_")
            path = out / f"findings_{safe_name}.csv"
            all_df[all_df["category"] == cat].to_csv(path, index=False)
            written.append(str(path))

    # Object health
    health_rows = [
        {
            "object":        f"{r.obj.schema}.{r.obj.name}",
            "type":          r.obj.obj_type,
            "lines":         r.obj.lines,
            "health_score":  r.health_score,
            "critical":      r.severity_counts.get("Critical", 0),
            "high":          r.severity_counts.get("High", 0),
            "medium":        r.severity_counts.get("Medium", 0),
            "low":           r.severity_counts.get("Low", 0),
        }
        for r in result.object_results
    ]
    if health_rows:
        path = out / "object_health.csv"
        pd.DataFrame(health_rows).to_csv(path, index=False)
        written.append(str(path))

    # Extended checks
    for key in ("tables_without_pk", "duplicate_indexes", "column_type_mismatches"):
        df = result.extended.get(key, pd.DataFrame())
        if not df.empty:
            path = out / f"{key}.csv"
            df.to_csv(path, index=False)
            written.append(str(path))

    # DMV files
    if dmv_results:
        for key, df in dmv_results.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                path = out / f"{key}.csv"
                df.to_csv(path, index=False)
                written.append(str(path))

    logger.info("CSV report written: %d files in %s", len(written), out)
    return written
