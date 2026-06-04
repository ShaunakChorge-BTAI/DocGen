"""
Phase 4: Change Request Service
Handles change request creation, approval workflow, and status management
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ChangeRequestService:
    """Service for change request workflow management"""

    def __init__(self, db):
        self.db = db
        self.approval_stages = [
            {"stage": 1, "role": "peer_review"},
            {"stage": 2, "role": "technical_lead"},
            {"stage": 3, "role": "dba"},
            {"stage": 4, "role": "compliance"}
        ]

    def create_change_request(
        self,
        finding_id: Optional[int],
        title: str,
        description: str,
        priority: str,
        user_id: int
    ) -> Dict:
        """Create a new change request"""
        try:
            # Generate CR ID
            query = text("""
                SELECT COALESCE(MAX(CAST(SUBSTRING(cr_id, 4) AS INTEGER)), 0) + 1
                FROM change_request_workflow
            """)
            result = self.db.execute(query)
            next_id = result.scalar()
            cr_id = f"CR-{next_id:05d}"

            insert_query = text("""
                INSERT INTO change_request_workflow
                (cr_id, finding_id, title, description, priority, created_by_user_id, status)
                VALUES (:cr_id, :finding_id, :title, :description, :priority, :user_id, 'draft')
                RETURNING id, cr_id, status
            """)
            result = self.db.execute(insert_query, {
                "cr_id": cr_id,
                "finding_id": finding_id,
                "title": title,
                "description": description,
                "priority": priority,
                "user_id": user_id
            })
            row = result.fetchone()
            self.db.commit()

            return {
                "cr_id": row[1],
                "title": title,
                "priority": priority,
                "status": row[2]
            }
        except Exception as e:
            logger.error(f"Error creating change request: {e}")
            raise

    def submit_change_request(self, cr_id: str) -> Dict:
        """Submit CR for approval"""
        try:
            # Update CR status
            update_query = text("""
                UPDATE change_request_workflow
                SET status = 'submitted'
                WHERE cr_id = :cr_id
                RETURNING cr_id, status
            """)
            result = self.db.execute(update_query, {"cr_id": cr_id})
            row = result.fetchone()

            if not row:
                raise ValueError(f"CR {cr_id} not found")

            # Create approval records for all stages
            for stage in self.approval_stages:
                approval_query = text("""
                    INSERT INTO cr_approvals
                    (cr_id, approval_stage, approval_role, status)
                    VALUES (:cr_id, :stage, :role, 'pending')
                """)
                self.db.execute(approval_query, {
                    "cr_id": cr_id,
                    "stage": stage["stage"],
                    "role": stage["role"]
                })

            self.db.commit()

            return {
                "cr_id": row[0],
                "status": row[1],
                "approval_stages_created": len(self.approval_stages)
            }
        except Exception as e:
            logger.error(f"Error submitting CR: {e}")
            raise

    def get_cr_approval_stages(self, cr_id: str) -> List[Dict]:
        """Get all approval stages for a CR"""
        try:
            query = text("""
                SELECT approval_stage, approval_role, status, assigned_to_user_id
                FROM cr_approvals
                WHERE cr_id = :cr_id
                ORDER BY approval_stage
            """)
            results = self.db.execute(query, {"cr_id": cr_id})

            stages = []
            for row in results:
                stages.append({
                    "stage": row[0],
                    "role": row[1],
                    "status": row[2],
                    "assigned_to_user_id": row[3]
                })
            return stages
        except Exception as e:
            logger.error(f"Error retrieving approval stages: {e}")
            return []

    def approve_at_stage(
        self,
        cr_id: str,
        stage: int,
        user_id: int,
        comment: Optional[str] = None
    ) -> Dict:
        """Approve CR at a specific stage"""
        try:
            approval_query = text("""
                UPDATE cr_approvals
                SET status = 'approved', approved_by_user_id = :user_id,
                    approval_date = NOW(), comment = :comment
                WHERE cr_id = :cr_id AND approval_stage = :stage
                RETURNING status
            """)
            result = self.db.execute(approval_query, {
                "cr_id": cr_id,
                "stage": stage,
                "user_id": user_id,
                "comment": comment
            })
            row = result.fetchone()

            if not row:
                raise ValueError(f"Approval stage {stage} not found for CR {cr_id}")

            # Check if all previous stages are approved
            check_query = text("""
                SELECT COUNT(*) FROM cr_approvals
                WHERE cr_id = :cr_id AND approval_stage < :stage AND status != 'approved'
            """)
            check_result = self.db.execute(check_query, {
                "cr_id": cr_id,
                "stage": stage
            })
            pending_count = check_result.scalar()

            can_proceed = pending_count == 0
            next_stage = stage + 1 if can_proceed and stage < len(self.approval_stages) else stage

            # Update CR current approval stage
            cr_query = text("""
                UPDATE change_request_workflow
                SET status = CASE
                    WHEN :next_stage > :total_stages THEN 'approved'
                    ELSE 'in_review'
                END
                WHERE cr_id = :cr_id
            """)
            self.db.execute(cr_query, {
                "cr_id": cr_id,
                "next_stage": next_stage,
                "total_stages": len(self.approval_stages)
            })
            self.db.commit()

            return {
                "cr_id": cr_id,
                "stage_status": row[0],
                "can_proceed_to_next": can_proceed,
                "next_stage": next_stage if can_proceed else None
            }
        except Exception as e:
            logger.error(f"Error approving CR: {e}")
            raise

    def reject_change_request(
        self,
        cr_id: str,
        stage: int,
        user_id: int,
        reason: str
    ) -> Dict:
        """Reject CR at a specific stage"""
        try:
            rejection_query = text("""
                UPDATE cr_approvals
                SET status = 'rejected', approved_by_user_id = :user_id,
                    approval_date = NOW(), comment = :reason
                WHERE cr_id = :cr_id AND approval_stage = :stage
                RETURNING status
            """)
            self.db.execute(rejection_query, {
                "cr_id": cr_id,
                "stage": stage,
                "user_id": user_id,
                "reason": reason
            })

            # Reset CR status to draft for resubmission
            cr_query = text("""
                UPDATE change_request_workflow
                SET status = 'draft'
                WHERE cr_id = :cr_id
                RETURNING status
            """)
            result = self.db.execute(cr_query, {"cr_id": cr_id})
            row = result.fetchone()
            self.db.commit()

            return {
                "cr_id": cr_id,
                "rejection_stage": stage,
                "cr_status_reset": row[0],
                "reason": reason
            }
        except Exception as e:
            logger.error(f"Error rejecting CR: {e}")
            raise

    def get_cr_details(self, cr_id: str) -> Optional[Dict]:
        """Get detailed information about a CR"""
        try:
            query = text("""
                SELECT id, cr_id, finding_id, title, description, priority, status,
                       created_by_user_id, created_at
                FROM change_request_workflow
                WHERE cr_id = :cr_id
            """)
            result = self.db.execute(query, {"cr_id": cr_id})
            row = result.fetchone()

            if not row:
                return None

            # Get approval stages
            stages = self.get_cr_approval_stages(cr_id)

            return {
                "cr_id": row[1],
                "finding_id": row[2],
                "title": row[3],
                "description": row[4],
                "priority": row[5],
                "status": row[6],
                "created_by_user_id": row[7],
                "created_at": str(row[8]),
                "approval_stages": stages
            }
        except Exception as e:
            logger.error(f"Error retrieving CR details: {e}")
            return None

    def list_pending_approvals(self, user_id: int, role: str) -> List[Dict]:
        """List pending CRs awaiting user's approval"""
        try:
            query = text("""
                SELECT DISTINCT crw.cr_id, crw.title, crw.priority, ca.approval_stage
                FROM change_request_workflow crw
                JOIN cr_approvals ca ON crw.cr_id = ca.cr_id
                WHERE ca.assigned_to_user_id = :user_id
                AND ca.approval_role = :role
                AND ca.status = 'pending'
                ORDER BY crw.priority DESC, ca.approval_stage
            """)
            results = self.db.execute(query, {
                "user_id": user_id,
                "role": role
            })

            crs = []
            for row in results:
                crs.append({
                    "cr_id": row[0],
                    "title": row[1],
                    "priority": row[2],
                    "approval_stage": row[3]
                })
            return crs
        except Exception as e:
            logger.error(f"Error listing pending approvals: {e}")
            return []

    def get_cr_by_status(self, status: str, limit: int = 50) -> List[Dict]:
        """Get CRs filtered by status"""
        try:
            query = text("""
                SELECT cr_id, title, priority, status, created_at
                FROM change_request_workflow
                WHERE status = :status
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {
                "status": status,
                "limit": limit
            })

            crs = []
            for row in results:
                crs.append({
                    "cr_id": row[0],
                    "title": row[1],
                    "priority": row[2],
                    "status": row[3],
                    "created_at": str(row[4])
                })
            return crs
        except Exception as e:
            logger.error(f"Error retrieving CRs by status: {e}")
            return []
