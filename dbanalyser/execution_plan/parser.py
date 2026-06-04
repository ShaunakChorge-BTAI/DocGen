"""
SQL Server Execution Plan Parser
==================================
Parses SQL Server XML Showplan (SET STATISTICS XML ON output) into a
structured tree of ExecutionPlanNode objects.

Supports both:
  - Full XML showplan  (xmlns=".../showplan/2012/11")
  - Estimated plan XML

Usage::

    with open("plan.xml") as f:
        xml_text = f.read()
    root = parse_execution_plan(xml_text)
    # root is an ExecutionPlanNode with .children, .cost, .operator, etc.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ExecutionPlanNode:
    """One physical operator node in the execution plan tree."""
    operator:          str               # e.g. "Clustered Index Scan"
    logical_op:        str               # e.g. "Index Scan"
    estimated_rows:    float             = 0.0
    actual_rows:       float             = 0.0
    estimated_cpu:     float             = 0.0
    estimated_io:      float             = 0.0
    subtree_cost:      float             = 0.0   # cumulative cost of this node + children
    node_id:           int               = 0
    parallel:          bool              = False
    warnings:          List[str]         = field(default_factory=list)
    table_name:        str               = ""
    index_name:        str               = ""
    seek_predicates:   List[str]         = field(default_factory=list)
    output_columns:    List[str]         = field(default_factory=list)
    children:          List["ExecutionPlanNode"] = field(default_factory=list)

    @property
    def own_cost(self) -> float:
        """Cost of this node alone (subtree minus children)."""
        child_cost = sum(c.subtree_cost for c in self.children)
        return max(0.0, self.subtree_cost - child_cost)

    @property
    def is_scan(self) -> bool:
        return "scan" in self.operator.lower()

    @property
    def is_seek(self) -> bool:
        return "seek" in self.operator.lower()

    @property
    def is_sort(self) -> bool:
        return "sort" in self.operator.lower()

    @property
    def is_hash_match(self) -> bool:
        return "hash match" in self.operator.lower()

    @property
    def is_nested_loops(self) -> bool:
        return "nested loops" in self.operator.lower()

    def all_nodes(self) -> List["ExecutionPlanNode"]:
        """Flatten this node + all descendants (DFS)."""
        result = [self]
        for child in self.children:
            result.extend(child.all_nodes())
        return result


# ── XML namespace helpers ─────────────────────────────────────────────────────

_NS_PATTERN = re.compile(r'\{[^}]+\}')


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from a tag name."""
    return _NS_PATTERN.sub("", tag)


def _attr(elem: ET.Element, name: str, default: str = "") -> str:
    """Get attribute, trying both with and without namespace."""
    return elem.get(name, elem.get(_strip_ns(name), default))


def _float(val: str, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Core parser ───────────────────────────────────────────────────────────────

def parse_execution_plan(xml_text: str) -> Optional[ExecutionPlanNode]:
    """
    Parse a SQL Server XML execution plan into an ExecutionPlanNode tree.

    Args:
        xml_text: Raw XML string from SET STATISTICS XML ON or
                  estimated plan (Ctrl+L in SSMS).

    Returns:
        Root ExecutionPlanNode, or None if parsing fails.
    """
    if not xml_text or not xml_text.strip():
        return None

    # Strip BOM if present
    xml_text = xml_text.lstrip('\ufeff')

    try:
        root_elem = ET.fromstring(xml_text)
    except ET.ParseError:
        # Try stripping namespace declarations that confuse some parsers
        cleaned = re.sub(r' xmlns[^"]*"[^"]*"', '', xml_text)
        try:
            root_elem = ET.fromstring(cleaned)
        except ET.ParseError:
            return None

    # Find the first RelOp (root operator) — search by stripped tag name
    rel_op = _find_first_relop(root_elem)
    if rel_op is None:
        return None

    return _parse_relop(rel_op)


def _find_first_relop(elem: ET.Element) -> Optional[ET.Element]:
    """BFS search for the first RelOp element (the plan root operator)."""
    queue = [elem]
    while queue:
        current = queue.pop(0)
        if _strip_ns(current.tag) == "RelOp":
            return current
        queue.extend(list(current))
    return None


def _parse_relop(elem: ET.Element, depth: int = 0) -> ExecutionPlanNode:
    """Recursively parse a RelOp element into an ExecutionPlanNode."""
    operator   = elem.get("PhysicalOp", elem.get("LogicalOp", "Unknown"))
    logical_op = elem.get("LogicalOp", operator)
    node_id    = int(elem.get("NodeId", "0") or "0")
    est_rows   = _float(elem.get("EstimateRows", "0"))
    est_cpu    = _float(elem.get("EstimateCPU", "0"))
    est_io     = _float(elem.get("EstimateIO", "0"))
    subtree    = _float(elem.get("EstimatedTotalSubtreeCost", "0"))
    parallel   = elem.get("Parallel", "0") == "1"

    node = ExecutionPlanNode(
        operator=operator,
        logical_op=logical_op,
        estimated_rows=est_rows,
        estimated_cpu=est_cpu,
        estimated_io=est_io,
        subtree_cost=subtree,
        node_id=node_id,
        parallel=parallel,
    )

    # Walk child elements
    for child in elem:
        tag = _strip_ns(child.tag)

        if tag == "RelOp":
            node.children.append(_parse_relop(child, depth + 1))

        elif tag in ("IndexScan", "TableScan", "ClusteredIndexScan",
                      "IndexSeek", "ClusteredIndexSeek"):
            node.table_name = (
                child.get("Table", "")
                or child.get("Database", "")  # fallback
            )
            # Object element
            for obj_elem in child:
                if _strip_ns(obj_elem.tag) == "Object":
                    node.table_name  = obj_elem.get("Table", node.table_name)
                    node.index_name  = obj_elem.get("Index", "")

        elif tag == "Warnings":
            for w in child:
                warn_tag = _strip_ns(w.tag)
                if warn_tag == "NoJoinPredicate":
                    node.warnings.append("NoJoinPredicate")
                elif warn_tag == "SpillWarning":
                    node.warnings.append("SpillWarning")
                elif warn_tag == "PlanAffectingConvert":
                    col = w.get("Expression", "")
                    node.warnings.append(f"ImplicitConversion:{col}")
                else:
                    node.warnings.append(warn_tag)

        elif tag == "OutputList":
            for col in child:
                col_ref = _strip_ns(col.tag)
                if col_ref == "ColumnReference":
                    col_name = (
                        child.get("Column", "")
                        or col.get("Column", "")
                    )
                    if col_name:
                        node.output_columns.append(col_name)

        elif tag in ("SeekPredicates", "Predicate"):
            # Simplified — just record the sub-element count
            for sp in child:
                spstr = ET.tostring(sp, encoding="unicode")
                # Extract simple ScalarOperator text
                text = re.sub(r'<[^>]+>', ' ', spstr).strip()[:120]
                if text:
                    node.seek_predicates.append(text)

        # Recurse into non-RelOp containers that hold nested RelOps
        elif tag not in ("Object", "ColumnReference", "ScalarOperator"):
            for grand in child:
                if _strip_ns(grand.tag) == "RelOp":
                    node.children.append(_parse_relop(grand, depth + 1))

    return node


# ── Text plan fallback ────────────────────────────────────────────────────────

def parse_text_plan(text: str) -> List[str]:
    """
    Extract a simplified list of operator lines from a text execution plan
    (the output of SET SHOWPLAN_TEXT ON).

    Returns a list of stripped lines that describe operators.
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            lines.append(stripped)
    return lines
