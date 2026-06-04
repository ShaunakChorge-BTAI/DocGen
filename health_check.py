"""DBAnalyser Installation Health Check — run with: python health_check.py"""
import json
import sys
import tomllib
from unittest.mock import MagicMock, patch

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(n, label):
    def decorator(fn):
        try:
            fn()
            results.append((n, label, PASS, ""))
            print(f"  {n:2d}. {label:<38} {PASS}")
        except Exception as exc:
            results.append((n, label, FAIL, str(exc)))
            print(f"  {n:2d}. {label:<38} {FAIL}  << {exc}")
    return decorator


print()
print("=" * 56)
print("  DBAnalyser — Installation Health Check")
print("=" * 56)
print()

# ── 1. Config ─────────────────────────────────────────────────────────────────
@check(1, "Config (all 10 sections, YAML)")
def _():
    from dbanalyser.config import load_config, Settings, AIOptimizerConfig
    cfg = load_config("analysis_config.yaml")
    assert isinstance(cfg, Settings)
    assert isinstance(cfg.ai_optimizer, AIOptimizerConfig)
    assert cfg.ai_optimizer.model == "claude-3-5-haiku-20241022"
    assert cfg.ai_optimizer.persist_results is True
    assert cfg.ai_optimizer.include_schema is True
    assert cfg.ai_optimizer.max_tokens == 4096
    assert cfg.ai_optimizer.temperature == 0.1
    assert cfg.auth.algorithm == "HS256"
    assert cfg.notifications.enabled is False
    assert cfg.scheduler.enabled is False


# ── 2. Schema Intel embedder ──────────────────────────────────────────────────
@check(2, "Schema Intel embedder (256-dim TF-IDF)")
def _():
    from dbanalyser.schema_intel.embedder import (
        embed_schema_object, cosine_similarity, vector_to_json, vector_from_json,
    )
    v1 = embed_schema_object("table", "Accounts", "", "CREATE TABLE dbo.Accounts")
    v2 = embed_schema_object("table", "Orders", "", "CREATE TABLE dbo.Orders")
    assert len(v1) == 256
    assert v1 != v2
    assert vector_from_json("") == []
    assert vector_from_json("null") == []
    assert vector_from_json(vector_to_json(v1)) == v1
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-6
    assert cosine_similarity([0.0, 0.0], [1.0, 0.5]) == 0.0


# ── 3. Schema Intel extractor ─────────────────────────────────────────────────
@check(3, "Schema Intel extractor (file-based)")
def _():
    from dbanalyser.schema_intel.extractor import extract_schema_from_objects
    obj = MagicMock()
    obj.name = "Accounts"; obj.obj_type = "table"; obj.schema = "dbo"
    obj.source = "CREATE TABLE dbo.Accounts (\n  Id INT NOT NULL,\n  Name varchar(100)\n)"
    results = extract_schema_from_objects([obj])
    assert any(r.object_type == "table" for r in results)
    assert any(r.object_type == "column" for r in results)
    # Proc extraction
    obj2 = MagicMock()
    obj2.name = "usp_Get"; obj2.obj_type = "stored procedure"; obj2.schema = "dbo"
    obj2.source = "CREATE PROCEDURE dbo.usp_Get AS BEGIN SELECT 1 END"
    r2 = extract_schema_from_objects([obj2])
    assert any(r.object_type == "procedure" for r in r2)


# ── 4. Schema Intel searcher ──────────────────────────────────────────────────
@check(4, "Schema Intel searcher (cosine similarity)")
def _():
    from dbanalyser.schema_intel.embedder import embed_schema_object
    from dbanalyser.schema_intel.searcher import search_schema, build_schema_context_for_object
    candidates = [
        {"object_type": "table", "schema_name": "dbo", "object_name": "Accounts",
         "parent_name": "", "definition": "accounts",
         "embedding": embed_schema_object("table", "Accounts", "", "accounts")},
        {"object_type": "table", "schema_name": "dbo", "object_name": "Orders",
         "parent_name": "", "definition": "orders",
         "embedding": embed_schema_object("table", "Orders", "", "orders")},
    ]
    with patch("dbanalyser.schema_intel.repository.get_embeddings_for_db",
               return_value=candidates):
        res = search_schema("Accounts", top_k=5)
    assert len(res) > 0
    assert all("similarity_score" in r for r in res)
    with patch("dbanalyser.schema_intel.searcher.search_schema", return_value=[]):
        ctx = build_schema_context_for_object("usp_X", "SELECT 1")
    assert "not available" in ctx.lower() or "no schema" in ctx.lower()


# ── 5. Execution plan parser ──────────────────────────────────────────────────
@check(5, "Execution plan parser (XML ShowPlan)")
def _():
    from dbanalyser.execution_plan.parser import parse_execution_plan, ExecutionPlanNode
    xml = (
        '<ShowPlanXML><BatchSequence><Batch><Statements><StmtSimple><QueryPlan>'
        '<RelOp NodeId="0" PhysicalOp="Clustered Index Scan"'
        ' LogicalOp="Clustered Index Scan"'
        ' EstimateRows="5000" EstimateCPU="0.05" EstimateIO="1.2"'
        ' EstimatedTotalSubtreeCost="1.25"/>'
        '</QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>'
    )
    root = parse_execution_plan(xml)
    assert root is not None
    assert isinstance(root, ExecutionPlanNode)
    assert root.is_scan
    assert abs(root.subtree_cost - 1.25) < 0.001
    assert root.estimated_rows == 5000.0
    assert parse_execution_plan("") is None
    assert parse_execution_plan("not xml at all") is None


# ── 6. Execution plan analyzer ────────────────────────────────────────────────
@check(6, "Execution plan analyzer (bottleneck detection)")
def _():
    from dbanalyser.execution_plan.analyzer import analyze_plan, PlanAnalysis, format_bottlenecks_text
    xml = (
        '<ShowPlanXML><BatchSequence><Batch><Statements><StmtSimple><QueryPlan>'
        '<RelOp NodeId="0" PhysicalOp="Table Scan" LogicalOp="Table Scan"'
        ' EstimateRows="10000" EstimateCPU="0.1" EstimateIO="3.5"'
        ' EstimatedTotalSubtreeCost="3.6"/>'
        '</QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>'
    )
    analysis = analyze_plan(xml)
    assert isinstance(analysis, PlanAnalysis)
    assert analysis.node_count >= 1
    assert len(analysis.table_scans) >= 1
    assert analysis.has_issues
    assert 0 <= analysis.complexity_score <= 100
    assert len(analysis.summary) > 0
    assert len(analysis.bottlenecks) >= 1
    failed = analyze_plan("garbage input")
    assert "parse" in failed.summary.lower() or "failed" in failed.summary.lower()
    txt = format_bottlenecks_text(analysis)
    assert isinstance(txt, str) and len(txt) > 0


# ── 7. AI optimizer context builder ──────────────────────────────────────────
@check(7, "AI optimizer context builder")
def _():
    from dbanalyser.ai_optimizer.context_builder import build_optimization_context
    good = "## Schema Context for usp_X\n### dbo.Accounts (table)\n  - Id int  NOT NULL  "
    findings = [{"rule_id": "PERF001", "severity": "High", "issue": "SELECT *"}]
    with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
               return_value=good):
        ctx_good = build_optimization_context(
            "usp_X", "SELECT * FROM Accounts",
            findings=findings, execution_plan="Cost=1.25",
        )
        ctx_partial = build_optimization_context("usp_X", "SELECT * FROM Accounts")
    with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
               return_value="## Schema Context\n*not available*"):
        ctx_none = build_optimization_context("usp_Z", "SELECT 1")
    assert ctx_good["context_quality"] == "good"
    assert ctx_partial["context_quality"] in ("partial", "good")
    assert ctx_none["context_quality"] == "none"
    for key in ("schema_context", "findings", "execution_plan", "context_quality", "warnings"):
        assert key in ctx_good
    assert ctx_partial["warnings"]   # missing plan + findings warnings


# ── 8. AI optimizer (mocked Anthropic API) ────────────────────────────────────
@check(8, "AI optimizer — mocked Anthropic API call")
def _():
    from dbanalyser.ai_optimizer.optimizer import (
        optimize_sql_object, OptimizationResult, _format_reasoning,
    )
    good = "## Schema Context for usp_X\n### dbo.Accounts (table)\n  - Id int  NOT NULL  "
    mock_mod = MagicMock()
    mock_msg = MagicMock()
    mock_msg.usage.input_tokens = 400
    mock_msg.usage.output_tokens = 200
    mock_msg.content = [MagicMock(text=json.dumps({
        "optimized_sql": "SELECT Id FROM dbo.Accounts WITH (NOLOCK)",
        "reasoning": "Replaced SELECT * — reduces I/O significantly.",
        "changes": [{"type": "performance", "before": "SELECT *",
                     "after": "SELECT Id", "impact": "Reduced I/O"}],
        "confidence_score": 0.88,
        "no_change_needed": False,
        "no_change_reason": "",
    }))]
    mock_mod.Anthropic.return_value.messages.create.return_value = mock_msg
    sys.modules["anthropic"] = mock_mod
    try:
        result = optimize_sql_object(
            "usp_X", "SELECT * FROM dbo.Accounts",
            schema_context=good,
            findings=[{"rule_id": "PERF001", "severity": "High", "issue": "SELECT *"}],
            api_key="sk-test", persist=False,
        )
        assert isinstance(result, OptimizationResult)
        assert result.error is None
        assert "Id" in result.optimized_sql
        assert abs(result.confidence_score - 0.88) < 0.01
        assert result.tokens_used == 600
        # no api key
        r2 = optimize_sql_object("usp_X", "SELECT 1", schema_context=good,
                                  api_key="", persist=False)
        assert r2.error is not None and "api key" in r2.error.lower()
    finally:
        del sys.modules["anthropic"]
    # _format_reasoning
    txt = _format_reasoning({"no_change_needed": True, "no_change_reason": "Already optimal."})
    assert "No optimization needed" in txt


# ── 9. Audit package ─────────────────────────────────────────────────────────
@check(9, "Audit package (logger + repository)")
def _():
    import inspect
    from dbanalyser.audit.logger import log_action
    from dbanalyser.audit.repository import get_audit_logs, count_audit_logs, AuditEntry
    sig = inspect.signature(log_action)
    for param in ("username", "action", "resource_type", "resource_id", "details", "ip_address"):
        assert param in sig.parameters, f"Missing param: {param}"
    sig2 = inspect.signature(get_audit_logs)
    for param in ("username", "action", "resource_type", "limit", "offset"):
        assert param in sig2.parameters, f"Missing param: {param}"


# ── 10. CLI commands ──────────────────────────────────────────────────────────
@check(10, "CLI — all 14 commands registered")
def _():
    from dbanalyser.cli import main as cli_main
    from click.testing import CliRunner
    runner = CliRunner()
    commands = [
        "run", "report", "api", "validate",
        "init-db", "history", "diff", "db",
        "compliance-report", "schedule", "auth",
        "ingest", "optimize", "audit",
    ]
    for cmd in commands:
        r = runner.invoke(cli_main, [cmd, "--help"])
        assert r.exit_code == 0, f"dbanalyser {cmd} --help failed: {r.output[:200]}"


# ── 11. pyproject.toml optional deps ─────────────────────────────────────────
@check(11, "pyproject.toml [ai] + [embeddings] extras")
def _():
    with open("pyproject.toml", "rb") as f:
        toml = tomllib.load(f)
    opts = toml["project"]["optional-dependencies"]
    assert "ai" in opts, "Missing [ai] extra"
    assert any("anthropic" in d for d in opts["ai"]), "anthropic not in [ai] deps"
    assert "embeddings" in opts, "Missing [embeddings] extra"
    assert any("sentence-transformers" in d for d in opts["embeddings"])
    assert "all" in opts, "Missing [all] meta-extra"


# ── 12. analysis_config.yaml ai_optimizer section ────────────────────────────
@check(12, "analysis_config.yaml ai_optimizer section")
def _():
    from dbanalyser.config import load_config
    cfg = load_config("analysis_config.yaml")
    assert cfg.ai_optimizer.enabled is False
    assert cfg.ai_optimizer.model == "claude-3-5-haiku-20241022"
    assert cfg.ai_optimizer.max_tokens == 4096
    assert cfg.ai_optimizer.temperature == 0.1
    assert cfg.ai_optimizer.include_schema is True
    assert cfg.ai_optimizer.include_execution_plan is True
    assert cfg.ai_optimizer.persist_results is True


# ── 13. DB schema SQL syntax check ───────────────────────────────────────────
@check(13, "DB schema.sql new tables present")
def _():
    with open("dbanalyser/db/schema.sql", encoding="utf-8") as f:
        sql = f.read()
    for table in ("schema_objects", "ai_optimizations", "audit_logs", "pipeline_steps",
                  "scheduled_tasks", "jobs", "findings", "runs", "db_registry"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, f"Missing table: {table}"


# ── 14. Full test suite ───────────────────────────────────────────────────────
@check(14, "Full test suite (pytest)")
def _():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line", "--no-header"],
        capture_output=True, text=True, cwd=".",
    )
    last = r.stdout.strip().splitlines()
    summary = last[-1] if last else r.stderr
    assert r.returncode == 0, f"Tests failed:\n{summary}"
    assert "failed" not in summary.lower(), f"Failures in: {summary}"


# ── Summary ───────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, _, s, _ in results if s == PASS)
failed = sum(1 for _, _, s, _ in results if s == FAIL)

print("=" * 56)
if failed == 0:
    print(f"  All {passed} health checks PASSED")
else:
    print(f"  {passed} PASSED  |  {failed} FAILED")
    print()
    print("  Failed checks:")
    for n, label, status, err in results:
        if status == FAIL:
            print(f"    {n:2d}. {label}: {err}")
print("=" * 56)
print()
