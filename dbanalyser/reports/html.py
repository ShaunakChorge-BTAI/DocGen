"""HTML report generator — produces a single self-contained HTML file."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SEV_COLOUR = {
    "Critical": "#c0392b",
    "High":     "#e67e22",
    "Medium":   "#f39c12",
    "Low":      "#27ae60",
}


def _badge(severity: str) -> str:
    colour = _SEV_COLOUR.get(severity, "#7f8c8d")
    return (
        f'<span style="background:{colour};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8em;font-weight:600">{severity}</span>'
    )


def _df_to_html(df, max_rows: int = 500) -> str:
    if df is None or df.empty:
        return "<p><em>No data.</em></p>"
    return df.head(max_rows).to_html(
        index=False, border=0, classes="tbl", escape=True
    )


_CSS = """
<style>
  body { font-family: Segoe UI, sans-serif; margin: 0; background: #f4f6f8; color: #2c3e50; }
  header { background: #1a252f; color: #fff; padding: 18px 32px; }
  header h1 { margin: 0; font-size: 1.6rem; }
  header p  { margin: 4px 0 0; opacity:.7; font-size:.9rem; }
  .container { max-width: 1200px; margin: 24px auto; padding: 0 24px; }
  .kpi-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
  .kpi { background:#fff; border-radius:8px; padding:16px 24px; flex:1;
         min-width:130px; box-shadow:0 1px 4px rgba(0,0,0,.1); text-align:center; }
  .kpi .val { font-size: 2rem; font-weight: 700; }
  .kpi .lbl { font-size: .8rem; color: #7f8c8d; margin-top: 4px; }
  .critical { color: #c0392b; }
  .high     { color: #e67e22; }
  .medium   { color: #f39c12; }
  .low      { color: #27ae60; }
  .health   { color: #2980b9; }
  section { background:#fff; border-radius:8px; padding:20px 24px;
            margin-bottom:20px; box-shadow:0 1px 4px rgba(0,0,0,.1); }
  section h2 { margin-top:0; font-size:1.1rem; border-bottom:2px solid #ecf0f1;
               padding-bottom:8px; }
  .tbl { width:100%; border-collapse:collapse; font-size:.85rem; }
  .tbl th { background:#2c3e50; color:#fff; padding:8px 12px; text-align:left; }
  .tbl td { padding:6px 12px; border-bottom:1px solid #ecf0f1; vertical-align:top; }
  .tbl tr:hover td { background:#f8f9fa; }
  footer { text-align:center; padding:24px; color:#7f8c8d; font-size:.8rem; }
</style>
"""


def generate_html(
        result,
        output_path: str,
        dmv_results: Optional[dict] = None,
) -> str:
    """Write a self-contained HTML report.  Returns the output file path."""
    import time

    sev = result.severity_counts
    health_class = (
        "critical" if result.overall_health < 50 else
        "high"     if result.overall_health < 70 else
        "medium"   if result.overall_health < 85 else
        "health"
    )

    # ── KPI block ─────────────────────────────────────────────────────────
    kpis_html = f"""
<div class="kpi-row">
  <div class="kpi"><div class="val health">{result.overall_health}</div><div class="lbl">Health Score</div></div>
  <div class="kpi"><div class="val">{result.total_objects}</div><div class="lbl">Objects Scanned</div></div>
  <div class="kpi"><div class="val">{result.total_findings}</div><div class="lbl">Total Findings</div></div>
  <div class="kpi"><div class="val critical">{sev.get('Critical',0)}</div><div class="lbl">Critical</div></div>
  <div class="kpi"><div class="val high">{sev.get('High',0)}</div><div class="lbl">High</div></div>
  <div class="kpi"><div class="val medium">{sev.get('Medium',0)}</div><div class="lbl">Medium</div></div>
  <div class="kpi"><div class="val low">{sev.get('Low',0)}</div><div class="lbl">Low</div></div>
</div>
"""

    # ── All findings table ────────────────────────────────────────────────
    all_df = result.all_findings_df()
    if not all_df.empty:
        # Inject badge HTML for severity column
        all_df = all_df.copy()
        all_df["severity"] = all_df["severity"].map(lambda s: _badge(s))
        findings_html = all_df.to_html(
            index=False, border=0, classes="tbl", escape=False
        )
    else:
        findings_html = "<p><em>No findings.</em></p>"

    # ── Object health table ───────────────────────────────────────────────
    import pandas as pd
    health_rows = [
        {
            "Object":   f"{r.obj.schema}.{r.obj.name}",
            "Type":     r.obj.obj_type,
            "Lines":    r.obj.lines,
            "Health":   r.health_score,
            "Critical": r.severity_counts.get("Critical", 0),
            "High":     r.severity_counts.get("High", 0),
            "Medium":   r.severity_counts.get("Medium", 0),
            "Low":      r.severity_counts.get("Low", 0),
        }
        for r in result.object_results
    ]
    health_html = _df_to_html(pd.DataFrame(health_rows))

    # ── Extended checks ───────────────────────────────────────────────────
    ext_sections = ""
    for key, title in [
        ("tables_without_pk",      "Tables Without Primary Key"),
        ("duplicate_indexes",      "Duplicate Index Candidates"),
        ("column_type_mismatches", "Column Type Mismatches"),
    ]:
        df = result.extended.get(key)
        ext_sections += f"<section><h2>{title}</h2>{_df_to_html(df)}</section>\n"

    # ── DMV sections ──────────────────────────────────────────────────────
    dmv_sections = ""
    if dmv_results:
        for key, title in [
            ("dmv_missing_indexes", "Missing Index Recommendations"),
            ("dmv_slow_queries",    "Slowest Queries (by avg elapsed)"),
            ("dmv_wait_stats",      "Top Wait Statistics"),
            ("dmv_blocking_chains", "Active Blocking Chains"),
            ("dmv_table_sizes",     "Table Sizes"),
            ("dmv_index_usage",     "Index Usage Statistics"),
        ]:
            df = dmv_results.get(key)
            dmv_sections += f"<section><h2>Live DB — {title}</h2>{_df_to_html(df, 30)}</section>\n"

    # ── Assemble full page ────────────────────────────────────────────────
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DBAnalyser Report — {result.run_label}</title>
  {_CSS}
</head>
<body>
<header>
  <h1>DBAnalyser — Analysis Report</h1>
  <p>Run: <strong>{result.run_label}</strong> &nbsp;|&nbsp; Generated: {ts} &nbsp;|&nbsp;
     Source: {result.source_mode} &nbsp;|&nbsp; Elapsed: {result.elapsed_sec}s</p>
</header>
<div class="container">
  {kpis_html}
  <section><h2>All Findings</h2>{findings_html}</section>
  <section><h2>Object Health Scores</h2>{health_html}</section>
  {ext_sections}
  {dmv_sections}
</div>
<footer>Generated by DBAnalyser &nbsp;|&nbsp; {ts}</footer>
</body>
</html>
"""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    logger.info("HTML report written to %s", path)
    return str(path)
