"""
Phase 5: Recommendations Engine
Analyzes findings and generates smart, actionable recommendations
"""

import logging
from typing import List, Dict, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


class RecommendationsEngine:
    """Service for generating smart recommendations based on assessment findings"""

    def __init__(self, db):
        self.db = db

    def generate_recommendations(
        self,
        assessment_run_id: int,
        max_recommendations: int = 50
    ) -> List[Dict]:
        """Generate recommendations based on assessment findings"""
        try:
            # Get findings from the assessment run
            findings_query = text("""
                SELECT f.id, f.severity, f.issue, f.finding_type
                FROM findings f
                WHERE f.finding_type = 'assessment'
                ORDER BY
                    CASE f.severity
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                    END
                LIMIT :limit
            """)
            findings_result = self.db.execute(findings_query, {"limit": max_recommendations})

            recommendations = []
            for finding_row in findings_result:
                finding_id = finding_row[0]
                severity = finding_row[1]
                issue = finding_row[2]

                # Determine recommendation type and priority
                if severity in ["Critical", "High"]:
                    rec_type = "immediate"
                    priority = 95 if severity == "Critical" else 75
                else:
                    rec_type = "priority" if severity == "Medium" else "future"
                    priority = 50 if severity == "Medium" else 30

                # Estimate effort based on issue type
                effort = self._estimate_effort(issue)
                benefit = self._estimate_benefit(severity)

                recommendation = {
                    "finding_id": finding_id,
                    "recommendation_type": rec_type,
                    "recommendation_text": self._generate_recommendation_text(issue, severity),
                    "implementation_effort": effort,
                    "estimated_benefit": benefit,
                    "priority_score": priority
                }

                # Store recommendation
                insert_query = text("""
                    INSERT INTO assessment_recommendations
                    (finding_id, recommendation_type, recommendation_text,
                     implementation_effort, estimated_benefit, priority_score)
                    VALUES (:finding_id, :type, :text, :effort, :benefit, :priority)
                    RETURNING id
                """)
                result = self.db.execute(insert_query, {
                    "finding_id": finding_id,
                    "type": rec_type,
                    "text": recommendation["recommendation_text"],
                    "effort": effort,
                    "benefit": benefit,
                    "priority": priority
                })
                recommendation["recommendation_id"] = result.fetchone()[0]

                recommendations.append(recommendation)

            self.db.commit()
            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    def get_quick_wins(
        self,
        assessment_run_id: int
    ) -> List[Dict]:
        """Identify quick wins: low effort, high impact items"""
        try:
            query = text("""
                SELECT id, finding_id, recommendation_text, implementation_effort,
                       estimated_benefit, priority_score
                FROM assessment_recommendations
                WHERE implementation_effort = 'low'
                AND estimated_benefit IN ('high', 'medium')
                ORDER BY priority_score DESC
                LIMIT 20
            """)
            results = self.db.execute(query)

            quick_wins = []
            for row in results:
                quick_wins.append({
                    "recommendation_id": row[0],
                    "finding_id": row[1],
                    "recommendation": row[2],
                    "effort": row[3],
                    "benefit": row[4],
                    "priority_score": row[5]
                })
            return quick_wins
        except Exception as e:
            logger.error(f"Error identifying quick wins: {e}")
            return []

    def get_recommendations_by_priority(
        self,
        rec_type: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get recommendations filtered by type and priority"""
        try:
            query = text("""
                SELECT id, finding_id, recommendation_text, implementation_effort,
                       estimated_benefit, priority_score, created_at
                FROM assessment_recommendations
                WHERE recommendation_type = :type
                ORDER BY priority_score DESC, created_at DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {
                "type": rec_type,
                "limit": limit
            })

            recommendations = []
            for row in results:
                recommendations.append({
                    "recommendation_id": row[0],
                    "finding_id": row[1],
                    "text": row[2],
                    "effort": row[3],
                    "benefit": row[4],
                    "priority": row[5],
                    "created_at": str(row[6])
                })
            return recommendations
        except Exception as e:
            logger.error(f"Error retrieving recommendations: {e}")
            return []

    def compare_assessments(
        self,
        database_id: int,
        baseline_run_id: int,
        current_run_id: int
    ) -> Dict:
        """Compare two assessment runs to identify improvements and regressions"""
        try:
            # Get baseline findings
            baseline_query = text("""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE severity = 'Critical')
                FROM findings
                WHERE assessment_id = :run_id
            """)
            baseline_result = self.db.execute(baseline_query, {"run_id": baseline_run_id})
            baseline_total, baseline_critical = baseline_result.fetchone()

            # Get current findings
            current_query = text("""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE severity = 'Critical')
                FROM findings
                WHERE assessment_id = :run_id
            """)
            current_result = self.db.execute(current_query, {"run_id": current_run_id})
            current_total, current_critical = current_result.fetchone()

            # Calculate differences
            total_improved = max(0, baseline_total - current_total)
            total_regressed = max(0, current_total - baseline_total)
            critical_increase = max(0, current_critical - baseline_critical)

            comparison = {
                "database_id": database_id,
                "baseline_run_id": baseline_run_id,
                "current_run_id": current_run_id,
                "baseline_findings": baseline_total,
                "current_findings": current_total,
                "findings_improved": total_improved,
                "findings_regressed": total_regressed,
                "findings_new": total_regressed,
                "critical_increase": critical_increase,
                "overall_trend": "improving" if total_improved > total_regressed else "declining"
            }

            # Store comparison
            insert_query = text("""
                INSERT INTO assessment_comparisons
                (database_id, baseline_run_id, current_run_id, comparison_date,
                 findings_improved, findings_regressed, findings_new, critical_increase)
                VALUES (:db_id, :baseline, :current, NOW(),
                        :improved, :regressed, :new, :critical)
                RETURNING id
            """)
            result = self.db.execute(insert_query, {
                "db_id": database_id,
                "baseline": baseline_run_id,
                "current": current_run_id,
                "improved": total_improved,
                "regressed": total_regressed,
                "new": total_regressed,
                "critical": critical_increase
            })
            comparison["comparison_id"] = result.fetchone()[0]
            self.db.commit()

            return comparison
        except Exception as e:
            logger.error(f"Error comparing assessments: {e}")
            raise

    def get_assessment_trend(
        self,
        database_id: int,
        days: int = 30
    ) -> List[Dict]:
        """Get trend data across multiple assessments"""
        try:
            query = text("""
                SELECT ar.run_date, ar.findings_count,
                       SUM(CASE WHEN f.severity = 'Critical' THEN 1 ELSE 0 END) as critical_count
                FROM assessment_runs ar
                LEFT JOIN findings f ON ar.id = f.assessment_id
                WHERE ar.run_date >= NOW() - INTERVAL :days
                GROUP BY ar.id, ar.run_date, ar.findings_count
                ORDER BY ar.run_date DESC
            """)
            results = self.db.execute(query, {"days": f"{days} days"})

            trends = []
            for row in results:
                trends.append({
                    "run_date": str(row[0]),
                    "findings": row[1],
                    "critical": row[2] or 0
                })
            return trends
        except Exception as e:
            logger.error(f"Error retrieving assessment trend: {e}")
            return []

    def _estimate_effort(self, issue: str) -> str:
        """Estimate implementation effort based on issue"""
        issue_lower = issue.lower()

        if any(word in issue_lower for word in ["index", "constraint", "grant"]):
            return "low"
        elif any(word in issue_lower for word in ["procedure", "function", "view"]):
            return "medium"
        elif any(word in issue_lower for word in ["schema", "migration", "refactor"]):
            return "high"
        else:
            return "medium"

    def _estimate_benefit(self, severity: str) -> str:
        """Estimate benefit based on severity"""
        if severity == "Critical":
            return "high"
        elif severity == "High":
            return "high"
        elif severity == "Medium":
            return "medium"
        else:
            return "low"

    def _generate_recommendation_text(self, issue: str, severity: str) -> str:
        """Generate human-readable recommendation text"""
        if severity == "Critical":
            urgency = "URGENT: "
        elif severity == "High":
            urgency = "HIGH PRIORITY: "
        else:
            urgency = ""

        action_map = {
            "index": "Add an index to improve query performance on",
            "constraint": "Add constraint validation to ensure data integrity for",
            "grant": "Review and update user permissions for",
            "procedure": "Optimize or refactor",
            "security": "Implement security hardening for",
            "performance": "Optimize performance of",
        }

        for key, action in action_map.items():
            if key in issue.lower():
                return f"{urgency}{action} {issue}"

        return f"{urgency}Address finding: {issue}"
