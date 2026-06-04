"""
Database Utilities for Optimization Testing
Executes queries on UAT database and compares results
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import text, event
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)

# Track query execution statistics
class QueryStats:
    def __init__(self):
        self.execution_time_ms = 0
        self.rows_returned = 0
        self.query_plan = None


async def execute_on_database(
    sql: str,
    session: Session,
    timeout_seconds: int = 30,
    explain_plan: bool = False,
) -> Dict[str, Any]:
    """
    Execute SQL on specified database (with timeout)

    Args:
        sql: SQL query to execute
        session: SQLAlchemy session
        timeout_seconds: Query timeout
        explain_plan: Whether to get EXPLAIN/ANALYZE output

    Returns:
        {
            "success": bool,
            "execution_time_ms": float,
            "row_count": int,
            "rows": list of result rows,
            "plan": query plan if explain_plan=True,
            "error": error message or None
        }
    """

    try:
        start_time = time.time()

        # Set statement timeout (PostgreSQL specific)
        session.execute(text(f"SET statement_timeout = {timeout_seconds * 1000}"))

        # Execute the query
        result = session.execute(text(sql))

        # Fetch results
        rows = result.fetchall()
        row_count = len(rows)

        execution_time_ms = (time.time() - start_time) * 1000

        # Get query plan if requested
        plan_text = None
        if explain_plan:
            plan_result = session.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}")
            )
            plan_rows = plan_result.fetchall()
            plan_text = "\n".join([str(row) for row in plan_rows])

        return {
            "success": True,
            "execution_time_ms": round(execution_time_ms, 2),
            "row_count": row_count,
            "rows": [dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
                     for row in rows],
            "plan": plan_text,
            "error": None,
        }

    except TimeoutError:
        return {
            "success": False,
            "execution_time_ms": timeout_seconds * 1000,
            "row_count": 0,
            "rows": [],
            "plan": None,
            "error": f"Query timeout after {timeout_seconds} seconds",
        }

    except Exception as e:
        logger.error(f"Query execution error: {e}")
        execution_time_ms = (time.time() - start_time) * 1000
        return {
            "success": False,
            "execution_time_ms": round(execution_time_ms, 2),
            "row_count": 0,
            "rows": [],
            "plan": None,
            "error": str(e),
        }


def compare_query_results(
    original_result: Dict[str, Any],
    optimized_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare two query execution results

    Returns:
        {
            "data_integrity_ok": bool,
            "row_count_matches": bool,
            "original_rows": int,
            "optimized_rows": int,
            "original_time_ms": float,
            "optimized_time_ms": float,
            "improvement_pct": float,  # positive = improvement
            "is_faster": bool,
            "error": str or None
        }
    """

    if not original_result["success"] or not optimized_result["success"]:
        return {
            "data_integrity_ok": False,
            "row_count_matches": False,
            "original_rows": original_result.get("row_count", 0),
            "optimized_rows": optimized_result.get("row_count", 0),
            "original_time_ms": original_result.get("execution_time_ms", 0),
            "optimized_time_ms": optimized_result.get("execution_time_ms", 0),
            "improvement_pct": 0,
            "is_faster": False,
            "error": f"Original: {original_result.get('error')}, Optimized: {optimized_result.get('error')}",
        }

    original_rows = original_result["row_count"]
    optimized_rows = optimized_result["row_count"]
    original_time = original_result["execution_time_ms"]
    optimized_time = optimized_result["execution_time_ms"]

    # Data integrity: must return same number of rows
    row_count_matches = original_rows == optimized_rows

    # Calculate improvement (negative = slower)
    if original_time > 0:
        improvement_pct = ((original_time - optimized_time) / original_time) * 100
    else:
        improvement_pct = 0

    return {
        "data_integrity_ok": row_count_matches,
        "row_count_matches": row_count_matches,
        "original_rows": original_rows,
        "optimized_rows": optimized_rows,
        "original_time_ms": round(original_time, 2),
        "optimized_time_ms": round(optimized_time, 2),
        "improvement_pct": round(improvement_pct, 2),
        "is_faster": optimized_time < original_time,
        "error": None if row_count_matches else "Row count mismatch - data integrity issue",
    }


def extract_query_plan_metrics(plan_text: str) -> Dict[str, Any]:
    """
    Parse EXPLAIN/ANALYZE output to extract metrics

    Returns:
        {
            "estimated_rows": int,
            "actual_rows": int,
            "execution_time_ms": float,
            "planning_time_ms": float,
            "buffers_hit": str,
            "most_expensive_nodes": [...]
        }
    """

    try:
        metrics = {
            "estimated_rows": 0,
            "actual_rows": 0,
            "execution_time_ms": 0,
            "planning_time_ms": 0,
            "buffers_hit": "N/A",
            "most_expensive_nodes": [],
        }

        lines = plan_text.split("\n")
        for line in lines:
            # Extract timing information
            if "Execution Time:" in line:
                time_str = line.split(":")[-1].strip().split()[0]
                metrics["execution_time_ms"] = float(time_str)
            elif "Planning Time:" in line:
                time_str = line.split(":")[-1].strip().split()[0]
                metrics["planning_time_ms"] = float(time_str)

            # Extract node info (simplified)
            if "Rows:" in line and "actual" in line:
                try:
                    # Extract: Rows: 1000 (estimated X) (actual Y)
                    actual_match = line.split("actual")[1].strip()
                    if actual_match.startswith("("):
                        actual_rows = int(actual_match.split()[0].replace("(", ""))
                        metrics["actual_rows"] = actual_rows
                except:
                    pass

        return metrics

    except Exception as e:
        logger.warning(f"Error parsing query plan: {e}")
        return {
            "estimated_rows": 0,
            "actual_rows": 0,
            "execution_time_ms": 0,
            "planning_time_ms": 0,
            "buffers_hit": "N/A",
            "most_expensive_nodes": [],
        }


def sanitize_sql(sql: str) -> str:
    """
    Sanitize SQL for safe execution (basic checks)

    Returns cleaned SQL or raises exception if dangerous
    """

    # Reject obvious dangerous operations
    dangerous_keywords = [
        "DROP",
        "DELETE",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "GRANT",
        "REVOKE",
        "INSERT",
        "UPDATE",
    ]

    upper_sql = sql.upper().strip()

    for keyword in dangerous_keywords:
        if upper_sql.startswith(keyword):
            raise ValueError(
                f"Optimization cannot run {keyword} statements. Use only SELECT queries."
            )

    # Remove leading/trailing whitespace and comments
    sql = sql.strip()
    if sql.startswith("--"):
        sql = "\n".join(
            [line for line in sql.split("\n") if not line.strip().startswith("--")]
        )

    return sql


def estimate_query_complexity(sql: str) -> Dict[str, Any]:
    """
    Estimate query complexity based on SQL analysis

    Returns:
        {
            "complexity_score": 0-100,
            "has_subqueries": bool,
            "has_joins": bool,
            "join_count": int,
            "table_count": int,
            "has_aggregation": bool,
            "estimated_execution_time_range": "fast|medium|slow|very_slow"
        }
    """

    upper_sql = sql.upper()

    # Count joins
    join_count = (
        upper_sql.count(" JOIN ")
        + upper_sql.count(" INNER JOIN ")
        + upper_sql.count(" LEFT JOIN ")
        + upper_sql.count(" RIGHT JOIN ")
        + upper_sql.count(" FULL JOIN ")
    )

    # Count tables (simplified - count FROMs)
    table_count = upper_sql.count(" FROM ") + upper_sql.count(",")

    # Features
    has_subqueries = "SELECT" in upper_sql[upper_sql.find("(") :] if "(" in upper_sql else False
    has_aggregation = any(
        agg in upper_sql for agg in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN(", "GROUP BY"]
    )
    has_window_functions = "OVER" in upper_sql
    has_cte = "WITH" in upper_sql

    # Calculate complexity score
    complexity_score = 0
    complexity_score += min(join_count * 15, 40)  # Joins: max 40 points
    complexity_score += min(table_count * 5, 20)  # Tables: max 20 points
    complexity_score += 15 if has_subqueries else 0
    complexity_score += 10 if has_aggregation else 0
    complexity_score += 10 if has_window_functions else 0
    complexity_score += 5 if has_cte else 0
    complexity_score = min(complexity_score, 100)

    # Estimate execution time range
    if complexity_score < 20:
        time_range = "fast"
    elif complexity_score < 50:
        time_range = "medium"
    elif complexity_score < 80:
        time_range = "slow"
    else:
        time_range = "very_slow"

    return {
        "complexity_score": complexity_score,
        "has_subqueries": has_subqueries,
        "has_joins": join_count > 0,
        "join_count": join_count,
        "table_count": table_count,
        "has_aggregation": has_aggregation,
        "has_window_functions": has_window_functions,
        "has_cte": has_cte,
        "estimated_execution_time_range": time_range,
    }
