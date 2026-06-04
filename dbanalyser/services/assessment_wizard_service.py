"""
Phase 5: Assessment Wizard Service
Handles multi-step wizard state management, scanning, and result processing
"""

import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import text
import json

logger = logging.getLogger(__name__)


class AssessmentWizardService:
    """Service for managing assessment wizard sessions and execution"""

    def __init__(self, db):
        self.db = db

    def start_assessment_session(
        self,
        user_id: int,
        template_id: Optional[int] = None
    ) -> Dict:
        """Start a new assessment wizard session"""
        try:
            session_token = str(uuid.uuid4())

            insert_query = text("""
                INSERT INTO assessment_sessions
                (session_token, user_id, current_step, status, started_at)
                VALUES (:token, :user_id, 1, 'in_progress', NOW())
                RETURNING id, session_token, current_step, status
            """)
            result = self.db.execute(insert_query, {
                "token": session_token,
                "user_id": user_id
            })
            row = result.fetchone()
            self.db.commit()

            return {
                "session_id": row[0],
                "session_token": row[1],
                "current_step": row[2],
                "status": row[3]
            }
        except Exception as e:
            logger.error(f"Error starting assessment session: {e}")
            raise

    def get_session_state(self, session_token: str) -> Optional[Dict]:
        """Get current state of a wizard session"""
        try:
            query = text("""
                SELECT id, user_id, current_step, selected_databases, assessment_config,
                       scan_progress, status, started_at
                FROM assessment_sessions
                WHERE session_token = :token
            """)
            result = self.db.execute(query, {"token": session_token})
            row = result.fetchone()

            if not row:
                return None

            return {
                "session_id": row[0],
                "user_id": row[1],
                "current_step": row[2],
                "selected_databases": json.loads(row[3]) if row[3] else [],
                "assessment_config": json.loads(row[4]) if row[4] else {},
                "scan_progress": row[5],
                "status": row[6],
                "started_at": str(row[7])
            }
        except Exception as e:
            logger.error(f"Error retrieving session state: {e}")
            return None

    def select_databases(
        self,
        session_token: str,
        database_ids: List[int]
    ) -> Dict:
        """Update selected databases and move to step 2"""
        try:
            update_query = text("""
                UPDATE assessment_sessions
                SET selected_databases = :databases, current_step = 2
                WHERE session_token = :token
                RETURNING id, current_step, selected_databases
            """)
            result = self.db.execute(update_query, {
                "token": session_token,
                "databases": json.dumps(database_ids)
            })
            row = result.fetchone()
            self.db.commit()

            if not row:
                raise ValueError(f"Session {session_token} not found")

            return {
                "session_id": row[0],
                "current_step": row[1],
                "databases_selected": len(database_ids),
                "selected_ids": database_ids
            }
        except Exception as e:
            logger.error(f"Error selecting databases: {e}")
            raise

    def configure_assessment(
        self,
        session_token: str,
        config: Dict
    ) -> Dict:
        """Save assessment configuration and move to step 3"""
        try:
            update_query = text("""
                UPDATE assessment_sessions
                SET assessment_config = :config, current_step = 3
                WHERE session_token = :token
                RETURNING id, current_step
            """)
            result = self.db.execute(update_query, {
                "token": session_token,
                "config": json.dumps(config)
            })
            row = result.fetchone()
            self.db.commit()

            if not row:
                raise ValueError(f"Session {session_token} not found")

            return {
                "session_id": row[0],
                "current_step": row[1],
                "configuration_saved": True
            }
        except Exception as e:
            logger.error(f"Error configuring assessment: {e}")
            raise

    def start_scan(self, session_token: str) -> Dict:
        """Begin assessment scan and move to step 4"""
        try:
            session = self.get_session_state(session_token)
            if not session:
                raise ValueError(f"Session {session_token} not found")

            # Create assessment run record
            insert_query = text("""
                INSERT INTO assessment_runs
                (session_id, run_date, databases_scanned, objects_scanned,
                 findings_count, status)
                VALUES (:session_id, NOW(), 0, 0, 0, 'in_progress')
                RETURNING id
            """)
            result = self.db.execute(insert_query, {
                "session_id": session["session_id"]
            })
            run_id = result.fetchone()[0]

            # Update session step
            update_query = text("""
                UPDATE assessment_sessions
                SET current_step = 4, scan_progress = 0
                WHERE session_token = :token
                RETURNING current_step
            """)
            self.db.execute(update_query, {"token": session_token})
            self.db.commit()

            return {
                "session_token": session_token,
                "run_id": run_id,
                "current_step": 4,
                "scan_started": True
            }
        except Exception as e:
            logger.error(f"Error starting scan: {e}")
            raise

    def update_scan_progress(
        self,
        session_token: str,
        progress: int
    ) -> Dict:
        """Update scan progress percentage"""
        try:
            update_query = text("""
                UPDATE assessment_sessions
                SET scan_progress = :progress
                WHERE session_token = :token
                RETURNING scan_progress, status
            """)
            result = self.db.execute(update_query, {
                "token": session_token,
                "progress": min(progress, 100)
            })
            row = result.fetchone()
            self.db.commit()

            if not row:
                raise ValueError(f"Session {session_token} not found")

            return {
                "session_token": session_token,
                "progress": row[0],
                "status": row[1]
            }
        except Exception as e:
            logger.error(f"Error updating scan progress: {e}")
            raise

    def get_scan_progress(self, session_token: str) -> Dict:
        """Get current scan progress"""
        try:
            query = text("""
                SELECT scan_progress, status, started_at
                FROM assessment_sessions
                WHERE session_token = :token
            """)
            result = self.db.execute(query, {"token": session_token})
            row = result.fetchone()

            if not row:
                return {"error": "Session not found"}

            progress = row[0]
            eta_seconds = int((100 - progress) * 30) if progress < 100 else 0

            return {
                "session_token": session_token,
                "percentage": progress,
                "status": row[1],
                "eta_seconds": eta_seconds
            }
        except Exception as e:
            logger.error(f"Error retrieving scan progress: {e}")
            raise

    def complete_scan(
        self,
        session_token: str,
        run_id: int,
        databases_scanned: int,
        objects_scanned: int,
        findings_count: int
    ) -> Dict:
        """Complete the scan and finalize results"""
        try:
            # Update assessment run
            run_query = text("""
                UPDATE assessment_runs
                SET databases_scanned = :db_count,
                    objects_scanned = :obj_count,
                    findings_count = :findings_count,
                    status = 'success'
                WHERE id = :run_id
                RETURNING status
            """)
            self.db.execute(run_query, {
                "db_count": databases_scanned,
                "obj_count": objects_scanned,
                "findings_count": findings_count,
                "run_id": run_id
            })

            # Update session
            session_query = text("""
                UPDATE assessment_sessions
                SET status = 'completed', completed_at = NOW(), scan_progress = 100
                WHERE session_token = :token
                RETURNING status
            """)
            self.db.execute(session_query, {"token": session_token})
            self.db.commit()

            return {
                "session_token": session_token,
                "run_id": run_id,
                "status": "completed",
                "findings_count": findings_count
            }
        except Exception as e:
            logger.error(f"Error completing scan: {e}")
            raise

    def get_assessment_results(self, session_token: str) -> Dict:
        """Get assessment results"""
        try:
            session = self.get_session_state(session_token)
            if not session:
                raise ValueError(f"Session {session_token} not found")

            # Get latest run
            run_query = text("""
                SELECT id, databases_scanned, objects_scanned, findings_count,
                       execution_time_ms, status, run_date
                FROM assessment_runs
                WHERE session_id = :session_id
                ORDER BY run_date DESC
                LIMIT 1
            """)
            run_result = self.db.execute(run_query, {
                "session_id": session["session_id"]
            })
            run_row = run_result.fetchone()

            if not run_row:
                return {"error": "No assessment results found"}

            return {
                "session_id": session["session_id"],
                "run_id": run_row[0],
                "databases_scanned": run_row[1],
                "objects_scanned": run_row[2],
                "findings_count": run_row[3],
                "execution_time_ms": run_row[4],
                "status": run_row[5],
                "run_date": str(run_row[6])
            }
        except Exception as e:
            logger.error(f"Error retrieving results: {e}")
            raise

    def cancel_assessment(self, session_token: str) -> Dict:
        """Cancel an ongoing assessment"""
        try:
            update_query = text("""
                UPDATE assessment_sessions
                SET status = 'cancelled', completed_at = NOW()
                WHERE session_token = :token
                RETURNING status
            """)
            result = self.db.execute(update_query, {"token": session_token})
            row = result.fetchone()
            self.db.commit()

            if not row:
                raise ValueError(f"Session {session_token} not found")

            return {
                "session_token": session_token,
                "status": row[0]
            }
        except Exception as e:
            logger.error(f"Error cancelling assessment: {e}")
            raise

    def get_assessment_history(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """Get past assessments for a user"""
        try:
            query = text("""
                SELECT ass.id, ass.run_date, ass.databases_scanned, ass.findings_count,
                       ass.status
                FROM assessment_runs ass
                JOIN assessment_sessions ases ON ass.session_id = ases.id
                WHERE ases.user_id = :user_id
                ORDER BY ass.run_date DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {
                "user_id": user_id,
                "limit": limit
            })

            history = []
            for row in results:
                history.append({
                    "run_id": row[0],
                    "run_date": str(row[1]),
                    "databases_scanned": row[2],
                    "findings_count": row[3],
                    "status": row[4]
                })
            return history
        except Exception as e:
            logger.error(f"Error retrieving assessment history: {e}")
            return []
