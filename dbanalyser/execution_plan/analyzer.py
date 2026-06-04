"""
Execution Plan Analyzer
========================
Takes a parsed ExecutionPlanNode tree and produces a PlanAnalysis with:
  - bottleneck nodes (highest cost share)
  - warnings (implicit conversions, missing seeks, spills)
  - table scan list
  - sort list
  - overall complexity score
  - human-readable summary
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .parser import ExecutionPlanNode, parse_execution_plan


# ── Analysis result ───────────────────────────────────────────────────────────

@dataclass
class BottleneckNode:
    """A high-cost operator worth investigating."""
    node_id:     int
    operator:    str
    table_name:  str
    cost_share:  float     # 0.0–1.0 fraction of total plan cost
    subtree_cost:float
    warnings:    List[str]
    reason:      str       # human-readable explanation


@dataclass
class PlanAnalysis:
    """Full analysis result for one execution plan."""
    total_cost:       float
    node_count:       int
    bottlenecks:      List[BottleneckNode]  = field(default_factory=list)
    table_scans:      List[str]             = field(default_factory=list)
    implicit_converts:List[str]             = field(default_factory=list)
    spill_warnings:   List[str]             = field(default_factory=list)
    missing_seeks:    List[str]             = field(default_factory=list)
    sort_operators:   List[str]             = field(default_factory=list)
    hash_joins:       List[str]             = field(default_factory=list)
    parallel_ops:     int                   = 0
    complexity_score: int                   = 0   # 0–100
    summary:          str                   = ""
    warnings:         List[str]             = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.table_scans or self.implicit_converts
            or self.spill_warnings or self.bottlenecks
        )


# ── Main analyzer ─────────────────────────────────────────────────────────────

def analyze_plan(
    plan_input: str | ExecutionPlanNode,
    bottleneck_threshold: float = 0.10,
) -> PlanAnalysis:
    """
    Analyze a SQL Server execution plan.

    Args:
        plan_input          : Either an XML string or an already-parsed
                              ExecutionPlanNode root.
        bottleneck_threshold: Nodes with cost_share >= this value are
                              flagged as bottlenecks (default 10%).

    Returns:
        PlanAnalysis with bottlenecks, warnings, and summary.
    """
    # ── Parse if needed ───────────────────────────────────────────────────────
    if isinstance(plan_input, str):
        root = parse_execution_plan(plan_input)
        if root is None:
            return PlanAnalysis(
                total_cost=0.0, node_count=0,
                summary="Could not parse execution plan XML.",
                warnings=["Plan parsing failed — provide valid XML showplan."],
            )
    else:
        root = plan_input

    all_nodes = root.all_nodes()
    total_cost = root.subtree_cost or 1e-9  # avoid div-by-zero

    analysis = PlanAnalysis(total_cost=total_cost, node_count=len(all_nodes))

    # ── Classify each node ────────────────────────────────────────────────────
    for node in all_nodes:
        cost_share = node.own_cost / total_cost

        # Table scans
        if node.is_scan:
            tbl = node.table_name or node.operator
            analysis.table_scans.append(tbl)
            if cost_share >= bottleneck_threshold:
                analysis.bottlenecks.append(BottleneckNode(
                    node_id=node.node_id,
                    operator=node.operator,
                    table_name=node.table_name,
                    cost_share=round(cost_share, 3),
                    subtree_cost=node.subtree_cost,
                    warnings=node.warnings,
                    reason=(
                        f"Full scan on '{tbl}' consuming "
                        f"{cost_share:.0%} of plan cost. "
                        "Consider adding or using a covering index."
                    ),
                ))

        # Sorts (often indicate missing index or ORDER BY forcing sort)
        if node.is_sort:
            analysis.sort_operators.append(node.operator)
            if cost_share >= bottleneck_threshold:
                analysis.bottlenecks.append(BottleneckNode(
                    node_id=node.node_id,
                    operator=node.operator,
                    table_name=node.table_name,
                    cost_share=round(cost_share, 3),
                    subtree_cost=node.subtree_cost,
                    warnings=node.warnings,
                    reason=(
                        f"Sort operator using {cost_share:.0%} of cost. "
                        "An index with matching ORDER BY clause may eliminate this."
                    ),
                ))

        # Hash joins (can be expensive and indicate missing indexes)
        if node.is_hash_match:
            analysis.hash_joins.append(node.operator)

        # Parallelism
        if node.parallel:
            analysis.parallel_ops += 1

        # Warnings
        for w in node.warnings:
            if "ImplicitConversion" in w:
                analysis.implicit_converts.append(w)
                analysis.warnings.append(
                    f"Implicit type conversion at node {node.node_id}: {w}. "
                    "This prevents index seeks — cast explicitly."
                )
            elif "SpillWarning" in w:
                analysis.spill_warnings.append(node.operator)
                analysis.warnings.append(
                    f"Spill to TempDB at node {node.node_id} ({node.operator}). "
                    "Increase work memory or reduce row set size."
                )
            elif "NoJoinPredicate" in w:
                analysis.warnings.append(
                    f"Cartesian product (no join predicate) at node {node.node_id}. "
                    "Verify JOIN conditions."
                )

        # High-cost non-scan/sort nodes
        if (cost_share >= bottleneck_threshold
                and not node.is_scan
                and not node.is_sort
                and not node.is_nested_loops):
            analysis.bottlenecks.append(BottleneckNode(
                node_id=node.node_id,
                operator=node.operator,
                table_name=node.table_name,
                cost_share=round(cost_share, 3),
                subtree_cost=node.subtree_cost,
                warnings=node.warnings,
                reason=(
                    f"{node.operator} consuming {cost_share:.0%} of plan cost."
                ),
            ))

    # De-duplicate bottlenecks by node_id
    seen_ids: set = set()
    unique_bottlenecks = []
    for b in sorted(analysis.bottlenecks, key=lambda x: -x.cost_share):
        if b.node_id not in seen_ids:
            seen_ids.add(b.node_id)
            unique_bottlenecks.append(b)
    analysis.bottlenecks = unique_bottlenecks[:10]

    # ── Complexity score ─────────────────────────────────────────────────────
    score = 0
    score += min(len(analysis.table_scans) * 15, 40)
    score += min(len(analysis.implicit_converts) * 10, 20)
    score += min(len(analysis.spill_warnings) * 15, 20)
    score += min(len(analysis.sort_operators) * 5, 10)
    score += min(len(analysis.hash_joins) * 3, 10)
    analysis.complexity_score = min(score, 100)

    # ── Summary ───────────────────────────────────────────────────────────────
    issues = []
    if analysis.table_scans:
        issues.append(f"{len(analysis.table_scans)} table/index scan(s)")
    if analysis.implicit_converts:
        issues.append(f"{len(analysis.implicit_converts)} implicit conversion(s)")
    if analysis.spill_warnings:
        issues.append(f"{len(analysis.spill_warnings)} TempDB spill(s)")
    if analysis.sort_operators:
        issues.append(f"{len(analysis.sort_operators)} sort operation(s)")
    if analysis.hash_joins:
        issues.append(f"{len(analysis.hash_joins)} hash join(s)")

    if issues:
        analysis.summary = (
            f"Plan cost {total_cost:.4f}  |  {len(all_nodes)} operators  |  "
            "Issues: " + ", ".join(issues) + "."
        )
    else:
        analysis.summary = (
            f"Plan cost {total_cost:.4f}  |  {len(all_nodes)} operators  |  "
            "No major issues detected."
        )

    return analysis


def format_bottlenecks_text(analysis: PlanAnalysis) -> str:
    """Format bottleneck list as a readable text block for AI prompts."""
    if not analysis.bottlenecks and not analysis.warnings:
        return analysis.summary

    lines = [analysis.summary, ""]
    if analysis.bottlenecks:
        lines.append("## Top Bottlenecks")
        for b in analysis.bottlenecks:
            lines.append(
                f"  - [Node {b.node_id}] {b.operator} "
                f"({b.cost_share:.0%} cost) — {b.reason}"
            )
    if analysis.warnings:
        lines.append("\n## Warnings")
        for w in analysis.warnings:
            lines.append(f"  - {w}")
    return "\n".join(lines)
