"""REST routes — /reports  (on-demand report generation & download)."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from dbanalyser.api.auth import AuthDep

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/download/{run_id}", dependencies=[AuthDep])
def download_report(
    run_id:  int,
    fmt:     str = Query("pdf", description="pdf | excel | html | json | csv"),
):
    """
    Generate and stream a report for a given run.
    The report is built on-the-fly from PostgreSQL data.
    """
    from dbanalyser.db.repository import get_run, get_findings
    import pandas as pd

    row = get_run(run_id=run_id)
    if not row:
        raise HTTPException(404, f"Run {run_id} not found.")

    df = get_findings(run_id)
    if isinstance(df, list):
        df = pd.DataFrame(df)

    label   = str(row.get("label", run_id)).replace(":", "-")
    tmp_dir = Path(tempfile.mkdtemp())

    if fmt == "excel":
        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows
        wb = Workbook()
        ws = wb.active
        ws.title = "Findings"
        if not df.empty:
            # df_excel = df.astype(str).fillna("")  # convert all to str for Excel export
            
            for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
                df[col] = df[col].dt.tz_localize(None)  # remove timezone for Excel compatibility
            
            for r in dataframe_to_rows(df, index=False, header=True):
                ws.append(r)
        # Summary sheet
        ws2 = wb.create_sheet("Summary")
        ws2.append(["Metric", "Value"])
        for k, v in [
            ("Run ID", row["id"]), ("Label", row.get("label","")),
            ("Health Score", row.get("health_score","")),
            ("Total Objects", row.get("total_objects",0)),
            ("Total Findings", row.get("total_issues",0)),
            ("Critical", row.get("critical_count",0)),
            ("High",     row.get("high_count",0)),
            ("Medium",   row.get("medium_count",0)),
            ("Low",      row.get("low_count",0)),
        ]:
            ws2.append([k, v])
        path = tmp_dir / f"dbanalyser_{label}.xlsx"
        wb.save(str(path))
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    elif fmt == "json":
        import json
        path = tmp_dir / f"dbanalyser_{label}.json"
        payload = {
            "run":      {k: str(v) for k, v in row.items()},
            "findings": df.fillna("").to_dict(orient="records") if not df.empty else [],
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        media = "application/json"

    elif fmt == "csv":
        path = tmp_dir / f"dbanalyser_{label}_findings.csv"
        df.to_csv(path, index=False)
        media = "text/csv"

    elif fmt == "html":
        path = tmp_dir / f"dbanalyser_{label}.html"
        html = f"<h1>DBAnalyser — Run {label}</h1>" + (
            df.to_html(index=False) if not df.empty else "<p>No findings.</p>"
        )
        path.write_text(html, encoding="utf-8")
        media = "text/html"

    elif fmt == "pdf":
        path = tmp_dir / f"dbanalyser_{label}.pdf"
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            )
            from reportlab.lib.units import cm

            doc    = SimpleDocTemplate(str(path), pagesize=A4,
                                       leftMargin=1.5*cm, rightMargin=1.5*cm,
                                       topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            story  = []

            # ── Title
            title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                         fontSize=16, spaceAfter=6)
            story.append(Paragraph(f"DBAnalyser — Report: {label}", title_style))
            story.append(Paragraph(
                f"Run ID: {row.get('id')}  |  "
                f"Health: {row.get('health_score', '—')}%  |  "
                f"Findings: {row.get('total_issues', 0)}",
                styles["Normal"],
            ))
            story.append(Spacer(1, 0.5*cm))

            # ── Summary table
            summary_data = [["Metric", "Value"]]
            for k, v in [
                ("Health Score", row.get("health_score", "—")),
                ("Total Objects", row.get("total_objects", 0)),
                ("Total Findings", row.get("total_issues", 0)),
                ("Critical", row.get("critical_count", 0)),
                ("High", row.get("high_count", 0)),
                ("Medium", row.get("medium_count", 0)),
                ("Low", row.get("low_count", 0)),
            ]:
                summary_data.append([k, str(v)])
            summary_tbl = Table(summary_data, colWidths=[5*cm, 5*cm])
            summary_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#630ed4")),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.HexColor("#f4f0ff"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c4b8e0")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(summary_tbl)
            story.append(Spacer(1, 0.5*cm))

            # ── Findings table
            if not df.empty:
                cols = ["severity", "category", "object_name", "rule_id", "issue"]
                present = [c for c in cols if c in df.columns]
                hdr  = [c.replace("_", " ").title() for c in present]
                rows_data = [hdr]
                SEV_BG = {
                    "Critical": colors.HexColor("#fee2e2"),
                    "High":     colors.HexColor("#fef3c7"),
                    "Medium":   colors.HexColor("#dbeafe"),
                    "Low":      colors.HexColor("#dcfce7"),
                }
                for _, r2 in df[present].head(500).iterrows():
                    rows_data.append([str(v)[:120] for v in r2.values])

                col_w = [2.5*cm, 3.5*cm, 4*cm, 2.5*cm, None]
                col_w = [w for w, c in zip(col_w, present) if c in present]

                fnd_tbl = Table(rows_data, colWidths=col_w, repeatRows=1)
                tbl_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#271f33")),
                    ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                    ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE",   (0, 0), (-1, -1), 7),
                    ("TOPPADDING",    (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c4b8e0")),
                ]
                for idx, row_vals in enumerate(rows_data[1:], start=1):
                    sev = str(row_vals[0]) if row_vals else ""
                    bg  = SEV_BG.get(sev, colors.HexColor("#f9f8fc"))
                    tbl_style.append(("BACKGROUND", (0, idx), (-1, idx), bg))
                fnd_tbl.setStyle(TableStyle(tbl_style))
                story.append(Paragraph("Findings", styles["Heading2"]))
                story.append(fnd_tbl)

            doc.build(story)
        except ImportError:
            raise HTTPException(
                503,
                "PDF generation requires 'reportlab'. "
                "Install it: pip install reportlab",
            )
        media = "application/pdf"

    else:
        raise HTTPException(400, f"Unsupported format '{fmt}'. Use excel|html|json|csv|pdf.")

    return FileResponse(
        path        = str(path),
        media_type  = media,
        filename    = path.name,
    )


@router.get("/health-gate/{run_id}", dependencies=[AuthDep])
def health_gate(
    run_id:         int,
    min_health:     float = Query(50.0, description="Minimum acceptable health score"),
    max_critical:   int   = Query(0,    description="Maximum allowed Critical findings"),
    max_high:       int   = Query(10,   description="Maximum allowed High findings"),
):
    """
    CI/CD gate endpoint.
    Returns HTTP 200 (pass) or HTTP 422 (fail) based on thresholds.
    Use this in your deployment pipeline to block bad releases.
    """
    from dbanalyser.db.repository import get_run
    row = get_run(run_id=run_id)
    if not row:
        raise HTTPException(404, f"Run {run_id} not found.")

    health   = float(row.get("health_score") or 0)
    critical = int(row.get("critical_count") or 0)
    high     = int(row.get("high_count")     or 0)

    failures = []
    if health   < min_health:   failures.append(f"Health {health} < threshold {min_health}")
    if critical > max_critical: failures.append(f"Critical {critical} > max {max_critical}")
    if high     > max_high:     failures.append(f"High {high} > max {max_high}")

    if failures:
        raise HTTPException(
            status_code=422,
            detail={"gate": "FAILED", "reasons": failures,
                    "health": health, "critical": critical, "high": high},
        )
    return {
        "gate":     "PASSED",
        "health":   health,
        "critical": critical,
        "high":     high,
    }
