"""
AI SQL Optimizer — Anthropic Claude Integration
================================================
Sends SQL objects (with schema context, execution plan, and rule findings)
to Claude for optimization suggestions.

ENFORCED BY CLAUDE.md:
  - Schema context MUST be fetched before every call.
  - Execution plan MUST be included if available.
  - All optimization decisions MUST be logged to ai_optimizations table.
  - NEVER call this without schema_context.

Configuration (analysis_config.yaml):
  ai_optimizer:
    enabled: true
    api_key: ""              # or DBANALYSER_AI_OPTIMIZER_API_KEY env var
    model: "claude-3-5-haiku-20241022"
    max_tokens: 4096
    temperature: 0.1
    include_schema: true
    include_execution_plan: true
    persist_results: true
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class OptimizationResult:
    """Full result of an AI optimization request."""
    object_name:        str
    original_sql:       str
    optimized_sql:      str              # the rewritten SQL
    reasoning:          str              # Claude's explanation
    schema_context_used:str              # schema that was included
    execution_plan_used:str              # execution plan that was included
    findings_used:      List[dict]       # rule findings that were included
    confidence_score:   float            # 0.0–1.0
    model_used:         str
    tokens_used:        int
    elapsed_sec:        float
    changes:            List[dict] = field(default_factory=list)  # optimization changes
    no_change_needed:   bool = False
    no_change_reason:   str = ""
    error:              Optional[str] = None


# ── Prompt builder ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert SQL Server database performance engineer and code quality analyst.
Your job is to analyse SQL Server stored procedures, views, and functions, then provide:
1. An optimized version of the SQL
2. A detailed explanation of every change made
3. The performance and correctness impact of each change
4. A confidence score (0.0–1.0) for your suggestions

RULES YOU MUST FOLLOW:
- Use the provided schema context — never assume table/column names
- Use the provided execution plan (if given) to identify actual bottlenecks
- Address the rule findings provided — they are verified issues
- Preserve all business logic exactly — do not change what the SQL does
- Keep SQL Server T-SQL dialect — do not use syntax from other databases
- Provide BEFORE and AFTER SQL clearly separated
- Always explain WHY each change improves the SQL
- If no optimization is possible, say so clearly"""


def _build_user_prompt(
    object_name:    str,
    source_sql:     str,
    schema_context: str,
    findings:       List[dict],
    execution_plan: str = "",
) -> str:
    findings_text = ""
    if findings:
        lines = [f"- [{f.get('severity','?')}] {f.get('rule_id','?')}: {f.get('issue','?')}"
                 for f in findings[:20]]
        findings_text = "\n## Rule Findings (verified issues to fix)\n" + "\n".join(lines)

    plan_text = ""
    if execution_plan:
        plan_text = f"\n## Execution Plan Summary\n```\n{execution_plan[:3000]}\n```"

    return f"""# Optimize SQL Object: {object_name}

{schema_context}
{findings_text}
{plan_text}

## SQL to Optimize
```sql
{source_sql}
```

## Your Task
1. Analyse the SQL above using the schema context, findings, and execution plan
2. Provide an optimized version addressing all issues found
3. Explain each change with before/after impact

## Response Format (JSON)
Respond with valid JSON only — no markdown, no extra text:
{{
  "optimized_sql": "<the complete optimized SQL>",
  "reasoning": "<detailed explanation of every change>",
  "changes": [
    {{
      "type": "performance|security|reliability|best_practice",
      "before": "<original snippet>",
      "after": "<optimized snippet>",
      "impact": "<why this helps>"
    }}
  ],
  "confidence_score": 0.85,
  "no_change_needed": false,
  "no_change_reason": ""
}}
"""


# ── Ollama Optimizer ─────────────────────────────────────────────────────────

def _build_ollama_prompt(
    object_name:    str,
    source_sql:     str,
    schema_context: str,
    findings:       List[dict],
    execution_plan: str = "",
) -> str:
    """Build prompt for Ollama optimization (similar to Claude but more concise)."""
    findings_text = ""
    if findings:
        lines = [f"- [{f.get('severity','?')}] {f.get('rule_id','?')}: {f.get('issue','?')}"
                 for f in findings[:10]]
        findings_text = "\nIssues to fix:\n" + "\n".join(lines)

    return f"""Optimize this SQL object: {object_name}

Schema context:
{schema_context[:1000]}

{findings_text}

SQL to optimize:
{source_sql}

Provide:
1. Optimized SQL
2. Brief explanation of changes
3. Confidence score (0.0-1.0)

Format response as JSON with keys: optimized_sql, reasoning, confidence_score"""


def _optimize_with_ollama(
    object_name:    str,
    source_sql:     str,
    schema_context: str,
    findings:       List[dict],
    execution_plan: str = "",
    max_tokens:     int = 4096,
    db_registry_id: Optional[int] = None,
    run_id:         Optional[int] = None,
    persist:        bool = True,
) -> Optional[OptimizationResult]:
    """Optimize SQL using Ollama (fast, local)."""
    t0 = time.time()
    findings = findings or []

    try:
        # Try to import requests for HTTP call to Ollama
        import requests  # type: ignore
    except ImportError:
        log.warning("requests package not installed, cannot use Ollama")
        return None

    # Get Ollama config
    try:
        from dbanalyser.config import load_config
        cfg = load_config()
        ollama_base_url = getattr(cfg.ai_optimizer, "ollama_base_url",
                                  "http://172.19.25.94:11434")
        ollama_model = getattr(cfg.ai_optimizer, "ollama_model", "llama3.1")
    except Exception:
        ollama_base_url = "http://172.19.25.94:11434"
        ollama_model = "llama3.1"

    optimized_sql = source_sql
    reasoning = ""
    confidence = 0.0
    error = None

    try:
        prompt = _build_ollama_prompt(
            object_name=object_name,
            source_sql=source_sql,
            schema_context=schema_context,
            findings=findings,
            execution_plan=execution_plan,
        )

        # Call Ollama API
        response = requests.post(
            f"{ollama_base_url}/api/generate",
            json={
                "model": ollama_model,
                "prompt": prompt,
                "temperature": 0.1,
                "num_predict": min(max_tokens, 2048),
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()

        raw = response.json().get("response", "").strip()

        # Parse response (attempt JSON extraction)
        if "{" in raw:
            try:
                json_part = raw[raw.index("{"):raw.rindex("}")+1]
                data = json.loads(json_part)
                optimized_sql = data.get("optimized_sql", source_sql)
                reasoning = data.get("reasoning", "")
                confidence = float(data.get("confidence_score", 0.6))
            except (json.JSONDecodeError, ValueError):
                reasoning = raw
                confidence = 0.5
        else:
            reasoning = raw
            confidence = 0.5

    except requests.exceptions.RequestException as exc:
        error = f"Ollama connection failed: {exc}"
        log.warning(error)
        return None
    except Exception as exc:
        error = str(exc)
        log.error("Ollama optimization failed for %s: %s", object_name, exc)
        return None

    elapsed = round(time.time() - t0, 2)
    result = OptimizationResult(
        object_name=object_name,
        original_sql=source_sql,
        optimized_sql=optimized_sql,
        reasoning=reasoning,
        schema_context_used=schema_context,
        execution_plan_used=execution_plan,
        findings_used=findings,
        confidence_score=confidence,
        model_used=ollama_model,
        tokens_used=0,  # Ollama doesn't track tokens easily
        elapsed_sec=elapsed,
        error=error,
    )

    # Persist to DB
    if persist:
        _persist_result(result, db_registry_id=db_registry_id, run_id=run_id)

    return result


# ── Main optimizer ────────────────────────────────────────────────────────────

def optimize_sql_object(
    object_name:    str,
    source_sql:     str,
    schema_context: str,
    findings:       List[dict] | None = None,
    execution_plan: str = "",
    api_key:        Optional[str] = None,
    model:          str = _DEFAULT_MODEL,
    max_tokens:     int = 4096,
    db_registry_id: Optional[int] = None,
    run_id:         Optional[int] = None,
    persist:        bool = True,
    optimization_mode: str = "advanced",  # "quick" (Ollama) or "advanced" (Claude)
    provider:       Optional[str] = None,  # Override provider (ollama | claude)
) -> OptimizationResult:
    """
    Send a SQL object to Claude or Ollama for AI optimization.

    PRECONDITIONS (enforced by CLAUDE.md):
      - schema_context MUST be non-empty (fetch via build_schema_context_for_object())
      - If execution plan is available, it MUST be passed via execution_plan parameter
      - All calls are logged to ai_optimizations table when persist=True

    Args:
        object_name       : name of the procedure/view/function
        source_sql        : full SQL source text
        schema_context    : output of build_schema_context_for_object() — REQUIRED
        findings          : list of RuleFinding dicts for this object
        execution_plan    : parsed execution plan text (optional but recommended)
        api_key           : Anthropic API key (falls back to env var ANTHROPIC_API_KEY)
        model             : Claude model to use
        max_tokens        : max response tokens
        db_registry_id    : for persistence
        run_id            : for persistence
        persist           : save result to ai_optimizations table
        optimization_mode : "quick" (Ollama) or "advanced" (Claude)
        provider          : override provider ("ollama" or "claude")

    Returns:
        OptimizationResult with optimized SQL, reasoning, and metadata.
    """
    # ── Route to appropriate provider ──────────────────────────────────────────
    actual_provider = provider
    if not actual_provider:
        actual_provider = "ollama" if optimization_mode == "quick" else "claude"

    log.info(f"optimize_sql_object: optimization_mode={optimization_mode!r}, actual_provider={actual_provider!r}")

    if actual_provider == "ollama":
        result = _optimize_with_ollama(
            object_name=object_name,
            source_sql=source_sql,
            schema_context=schema_context,
            findings=findings or [],
            execution_plan=execution_plan,
            max_tokens=max_tokens,
            db_registry_id=db_registry_id,
            run_id=run_id,
            persist=persist,
        )
        if result:
            return result
        # If Ollama explicitly requested and fails, don't fallback to Claude without API key
        if optimization_mode == "quick":
            return OptimizationResult(
                object_name=object_name, original_sql=source_sql,
                optimized_sql=source_sql, reasoning="",
                schema_context_used=schema_context,
                execution_plan_used=execution_plan, findings_used=findings or [],
                confidence_score=0.0, model_used="ollama", tokens_used=0,
                elapsed_sec=0.0, changes=[], no_change_needed=False, no_change_reason="",
                error="Ollama optimization service is not available. Make sure Ollama is running at the configured endpoint.",
            )
        # Fallback to Claude if advanced mode and Ollama fails
        log.warning("Ollama optimization failed for %s, falling back to Claude", object_name)
        actual_provider = "claude"

    # Default to Claude optimization
    # ── Enforce: schema context must be present ───────────────────────────────
    if not schema_context or schema_context.strip() == "":
        log.error(
            "CLAUDE.md VIOLATION: optimize_sql_object called without schema_context "
            "for object '%s'. Always call build_schema_context_for_object() first.",
            object_name,
        )
        schema_context = "## Schema Context\n*Schema not available — optimization limited.*"

    t0      = time.time()
    findings = findings or []

    # ── Resolve API key ───────────────────────────────────────────────────────
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("DBANALYSER_AI_OPTIMIZER_API_KEY", "")
    if not key:
        error_msg = "Anthropic API key not configured for Claude optimization. "
        if optimization_mode == "advanced":
            error_msg += "Set ANTHROPIC_API_KEY environment variable or use Quick (Ollama) mode instead."
        else:
            error_msg += "Please use Quick (Ollama) mode or provide an API key for advanced Claude mode."
        return OptimizationResult(
            object_name=object_name, original_sql=source_sql,
            optimized_sql=source_sql, reasoning="",
            schema_context_used=schema_context,
            execution_plan_used=execution_plan, findings_used=findings,
            confidence_score=0.0, model_used=model, tokens_used=0,
            elapsed_sec=0.0, changes=[], no_change_needed=False, no_change_reason="",
            error=error_msg,
        )

    # ── Call Anthropic API ────────────────────────────────────────────────────
    try:
        import anthropic   # type: ignore
    except ImportError:
        return OptimizationResult(
            object_name=object_name, original_sql=source_sql,
            optimized_sql=source_sql, reasoning="",
            schema_context_used=schema_context,
            execution_plan_used=execution_plan, findings_used=findings,
            confidence_score=0.0, model_used=model, tokens_used=0,
            elapsed_sec=0.0,
            error="anthropic package not installed. Run: pip install anthropic",
        )

    optimized_sql = source_sql
    reasoning     = ""
    confidence    = 0.0
    tokens_used   = 0
    error         = None

    try:
        client = anthropic.Anthropic(api_key=key)
        user_prompt = _build_user_prompt(
            object_name=object_name,
            source_sql=source_sql,
            schema_context=schema_context,
            findings=findings,
            execution_plan=execution_plan,
        )
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        raw         = message.content[0].text.strip()

        # Parse JSON response
        if raw.startswith("{"):
            data          = json.loads(raw)
            optimized_sql = data.get("optimized_sql", source_sql)
            reasoning     = _format_reasoning(data)
            confidence    = float(data.get("confidence_score", 0.7))
        else:
            # Model responded in plain text — extract SQL if possible
            reasoning  = raw
            confidence = 0.5

    except Exception as exc:
        error = str(exc)
        log.error("AI optimization failed for %s: %s", object_name, exc)

    elapsed = round(time.time() - t0, 2)
    result  = OptimizationResult(
        object_name=object_name, original_sql=source_sql,
        optimized_sql=optimized_sql, reasoning=reasoning,
        schema_context_used=schema_context,
        execution_plan_used=execution_plan, findings_used=findings,
        confidence_score=confidence, model_used=model,
        tokens_used=tokens_used, elapsed_sec=elapsed, error=error,
    )

    # ── Persist to DB ─────────────────────────────────────────────────────────
    if persist:
        _persist_result(result, db_registry_id=db_registry_id, run_id=run_id)

    return result


def _format_reasoning(data: dict) -> str:
    """Convert structured AI response into a human-readable reasoning string."""
    parts = []
    if data.get("no_change_needed"):
        parts.append(f"**No optimization needed:** {data.get('no_change_reason', '')}")
        return "\n".join(parts)

    if data.get("reasoning"):
        parts.append(data["reasoning"])

    changes = data.get("changes", [])
    if changes:
        parts.append("\n### Changes Made")
        for i, ch in enumerate(changes, 1):
            parts.append(
                f"\n**Change {i} ({ch.get('type', 'general')})**\n"
                f"- Before: `{ch.get('before', '')[:100]}`\n"
                f"- After:  `{ch.get('after', '')[:100]}`\n"
                f"- Impact: {ch.get('impact', '')}"
            )
    return "\n".join(parts)


def _persist_result(
    result: OptimizationResult,
    db_registry_id: Optional[int] = None,
    run_id:         Optional[int] = None,
) -> None:
    """Save optimization result to ai_optimizations table."""
    try:
        from dbanalyser.db.connection import get_cursor
        findings_json = json.dumps([
            {k: str(v) for k, v in f.items()}
            for f in (result.findings_used or [])[:20]
        ])
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO ai_optimizations
                    (run_id, object_name, original_sql, optimized_sql,
                     reasoning, schema_context_used, execution_plan_used,
                     confidence_score, model_used, tokens_used, findings_used)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                run_id,
                result.object_name,
                result.original_sql[:10000],
                result.optimized_sql[:10000],
                result.reasoning[:5000],
                result.schema_context_used[:5000],
                result.execution_plan_used[:5000],
                result.confidence_score,
                result.model_used,
                result.tokens_used,
                findings_json,
            ))
    except Exception as exc:
        log.warning("Could not persist optimization result: %s", exc)
