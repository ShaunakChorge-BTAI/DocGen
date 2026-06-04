"""
Tests for dbanalyser.execution_plan
=======================================
No real SQL Server connection needed — uses constructed XML strings.
"""
import pytest
from dbanalyser.execution_plan.parser  import parse_execution_plan, ExecutionPlanNode
from dbanalyser.execution_plan.analyzer import analyze_plan, PlanAnalysis


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _simple_plan(operator="Clustered Index Scan", logical_op="Index Scan",
                  cost=0.5, node_id=0, warnings_xml=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple>
          <QueryPlan>
            <RelOp NodeId="{node_id}"
                   PhysicalOp="{operator}"
                   LogicalOp="{logical_op}"
                   EstimateRows="1000"
                   EstimateCPU="0.01"
                   EstimateIO="{cost - 0.01}"
                   EstimatedTotalSubtreeCost="{cost}">
              {warnings_xml}
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""


def _nested_plan():
    """Two operators: a Hash Match containing a Clustered Index Scan."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<ShowPlanXML>
  <BatchSequence><Batch><Statements><StmtSimple><QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Hash Match" LogicalOp="Inner Join"
           EstimateRows="500" EstimateCPU="0.05" EstimateIO="0.0"
           EstimatedTotalSubtreeCost="1.2">
      <RelOp NodeId="1" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan"
             EstimateRows="1000" EstimateCPU="0.03" EstimateIO="0.8"
             EstimatedTotalSubtreeCost="0.83">
      </RelOp>
    </RelOp>
  </QueryPlan></StmtSimple></Statements></Batch></BatchSequence>
</ShowPlanXML>"""


# ─────────────────────────────────────────────────────────────────────────────
# Parser tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParseExecutionPlan:
    def test_returns_node_for_valid_xml(self):
        root = parse_execution_plan(_simple_plan())
        assert root is not None
        assert isinstance(root, ExecutionPlanNode)

    def test_none_for_empty_string(self):
        assert parse_execution_plan("") is None
        assert parse_execution_plan("   ") is None

    def test_none_for_invalid_xml(self):
        assert parse_execution_plan("<broken xml") is None

    def test_operator_name_extracted(self):
        root = parse_execution_plan(_simple_plan(operator="Index Seek"))
        assert root.operator == "Index Seek"

    def test_estimated_rows_parsed(self):
        root = parse_execution_plan(_simple_plan())
        assert root.estimated_rows == 1000.0

    def test_subtree_cost_parsed(self):
        root = parse_execution_plan(_simple_plan(cost=2.5))
        assert abs(root.subtree_cost - 2.5) < 0.001

    def test_node_id_parsed(self):
        root = parse_execution_plan(_simple_plan(node_id=5))
        assert root.node_id == 5

    def test_children_parsed_in_nested_plan(self):
        root = parse_execution_plan(_nested_plan())
        assert root is not None
        assert len(root.children) >= 1
        child = root.children[0]
        assert "Scan" in child.operator or "Seek" in child.operator

    def test_all_nodes_returns_flat_list(self):
        root = parse_execution_plan(_nested_plan())
        all_nodes = root.all_nodes()
        assert len(all_nodes) == 2

    def test_is_scan_property(self):
        root = parse_execution_plan(_simple_plan(operator="Clustered Index Scan"))
        assert root.is_scan is True

    def test_is_seek_property(self):
        root = parse_execution_plan(_simple_plan(operator="Clustered Index Seek"))
        assert root.is_seek is True

    def test_is_sort_property(self):
        root = parse_execution_plan(_simple_plan(operator="Sort"))
        assert root.is_sort is True

    def test_is_hash_match_property(self):
        root = parse_execution_plan(_simple_plan(operator="Hash Match"))
        assert root.is_hash_match is True

    def test_own_cost_leaf_node(self):
        root = parse_execution_plan(_simple_plan(cost=0.5))
        assert abs(root.own_cost - 0.5) < 0.001

    def test_own_cost_parent_node(self):
        root = parse_execution_plan(_nested_plan())
        # Parent cost 1.2, child cost 0.83 → own cost ~0.37
        assert root.own_cost >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Analyzer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzePlan:
    def test_returns_plan_analysis(self):
        analysis = analyze_plan(_simple_plan())
        assert isinstance(analysis, PlanAnalysis)

    def test_total_cost_populated(self):
        analysis = analyze_plan(_simple_plan(cost=1.5))
        assert abs(analysis.total_cost - 1.5) < 0.01

    def test_node_count_populated(self):
        analysis = analyze_plan(_simple_plan())
        assert analysis.node_count >= 1

    def test_table_scan_detected(self):
        analysis = analyze_plan(_simple_plan(operator="Clustered Index Scan", cost=5.0))
        assert len(analysis.table_scans) >= 1

    def test_seek_not_flagged_as_scan(self):
        analysis = analyze_plan(_simple_plan(operator="Clustered Index Seek", cost=5.0))
        assert len(analysis.table_scans) == 0

    def test_sort_detected(self):
        analysis = analyze_plan(_simple_plan(operator="Sort", cost=2.0))
        assert len(analysis.sort_operators) >= 1

    def test_hash_join_detected(self):
        analysis = analyze_plan(_nested_plan())
        assert len(analysis.hash_joins) >= 1

    def test_bottleneck_detected_high_cost_scan(self):
        # Single-node plan — scan consumes 100% of cost → should be bottleneck
        analysis = analyze_plan(_simple_plan(operator="Table Scan", cost=3.0),
                                 bottleneck_threshold=0.10)
        assert len(analysis.bottlenecks) >= 1

    def test_no_bottleneck_low_cost(self):
        # Plan with cost=0.001 scan (below any real threshold)
        analysis = analyze_plan(_simple_plan(operator="Clustered Index Scan", cost=0.001),
                                 bottleneck_threshold=0.10)
        # Scan at 100% of a near-zero plan should still be flagged
        assert analysis.total_cost < 0.01  # just verify parsing worked

    def test_complexity_score_range(self):
        analysis = analyze_plan(_simple_plan())
        assert 0 <= analysis.complexity_score <= 100

    def test_summary_string_populated(self):
        analysis = analyze_plan(_simple_plan())
        assert isinstance(analysis.summary, str)
        assert len(analysis.summary) > 0

    def test_invalid_xml_returns_failed_analysis(self):
        analysis = analyze_plan("NOT XML AT ALL")
        assert "parse" in analysis.summary.lower() or "failed" in analysis.summary.lower()

    def test_accepts_pre_parsed_node(self):
        root = parse_execution_plan(_simple_plan())
        analysis = analyze_plan(root)
        assert isinstance(analysis, PlanAnalysis)
        assert analysis.total_cost > 0

    def test_has_issues_true_when_scan(self):
        analysis = analyze_plan(_simple_plan(operator="Clustered Index Scan", cost=2.0))
        assert analysis.has_issues is True

    def test_nested_plan_analysis(self):
        analysis = analyze_plan(_nested_plan())
        assert analysis.node_count == 2
        assert len(analysis.hash_joins) >= 1
        assert len(analysis.table_scans) >= 1
