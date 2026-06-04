# Phase 4 Implementation Specification
## Database Management + Change Request Workflow

**Project:** DBAnalyser
**Phase:** 4 - Database Management & CR Workflow
**Duration:** 10 Working Days (1 week)
**Team Size:** 3-4 developers
**Date Created:** 2026-04-08
**Status:** Ready for Implementation

---

## Executive Summary

Phase 4 implements database lifecycle management, advanced change request workflow, and deployment tracking.

**Key Capabilities:**
- Database registration and lifecycle tracking
- Change request approval workflow with multi-stage approvals
- Deployment tracking and audit logs
- Rollback capability with version control
- Team-based approval routing
- Email notifications throughout workflow

---

## Phase 4 Deliverables

### 1. Database Schema (004_phase4_db_mgmt_schema.sql - 500 lines)

**New Tables:**
```sql
-- Database registry with lifecycle
CREATE TABLE database_versions (
  id SERIAL PRIMARY KEY,
  db_registry_id INT REFERENCES db_registry(id),
  version_number INT,
  version_date TIMESTAMP,
  patch_notes TEXT,
  deployed_by_user_id INT,
  deployed_at TIMESTAMP,
  is_rollback BOOLEAN DEFAULT false,
  rollback_target_version INT,
  created_at TIMESTAMP
);

-- Advanced CR workflow with multi-stage approvals
CREATE TABLE change_request_workflow (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100) UNIQUE,
  finding_id INT REFERENCES findings(id),
  optimization_id INT REFERENCES schema_object_optimizations(id),
  title TEXT NOT NULL,
  description TEXT,
  created_by_user_id INT,
  created_at TIMESTAMP,
  status VARCHAR(50) DEFAULT 'draft',  -- draft, submitted, in_review, approved, rejected, in_deployment, deployed
  priority VARCHAR(20),  -- low, medium, high, critical
  estimated_duration_mins INT,
  actual_duration_mins INT
);

-- Multi-stage approval process
CREATE TABLE cr_approvals (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
  approval_stage INT,  -- 1=peer, 2=lead, 3=dba, 4=compliance
  approval_role VARCHAR(100),  -- peer_review, technical_lead, dba, compliance
  assigned_to_user_id INT,
  approved_by_user_id INT,
  approval_date TIMESTAMP,
  comment TEXT,
  status VARCHAR(20),  -- pending, approved, rejected
  created_at TIMESTAMP
);

-- Deployment tracking and history
CREATE TABLE cr_deployments (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
  deployment_env VARCHAR(50),  -- staging, production
  deployment_date TIMESTAMP,
  deployed_by_user_id INT,
  deployment_duration_mins INT,
  status VARCHAR(50),  -- in_progress, success, failed, rolled_back
  error_details TEXT,
  pre_deployment_check_passed BOOLEAN,
  post_deployment_validation_passed BOOLEAN,
  rollback_available_until TIMESTAMP,
  created_at TIMESTAMP
);

-- Deployment audit trail
CREATE TABLE deployment_audit_log (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100),
  event_type VARCHAR(100),  -- status_change, approval, deployment, validation, rollback
  event_timestamp TIMESTAMP,
  user_id INT,
  details TEXT,
  created_at TIMESTAMP
);

-- Pre-deployment validation results
CREATE TABLE pre_deployment_checks (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
  check_type VARCHAR(100),  -- syntax, security, performance, compatibility
  check_result VARCHAR(50),  -- pass, fail, warning
  details TEXT,
  checked_at TIMESTAMP,
  created_at TIMESTAMP
);

-- Post-deployment validation
CREATE TABLE post_deployment_validation (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
  test_name VARCHAR(255),
  test_result VARCHAR(50),  -- passed, failed, skipped
  error_details TEXT,
  validated_at TIMESTAMP,
  validated_by_user_id INT,
  created_at TIMESTAMP
);

-- Rollback capability
CREATE TABLE deployment_rollback (
  id SERIAL PRIMARY KEY,
  cr_id VARCHAR(100),
  original_deployment_id INT REFERENCES cr_deployments(id),
  rollback_date TIMESTAMP,
  rollback_reason TEXT,
  rolled_back_by_user_id INT,
  rollback_status VARCHAR(50),  -- success, failed, pending
  created_at TIMESTAMP
);
```

---

### 2. Backend Services

**change_request_service.py (400 lines)**
```python
class ChangeRequestManager:
    def create_cr(finding_id, title, description, priority):
        # Generate CR ID
        # Set initial status to draft
        # Create approval stages

    def submit_cr(cr_id):
        # Validate CR completeness
        # Route to first approver
        # Send notifications

    def approve_cr(cr_id, stage, approver_id, comment):
        # Mark stage as approved
        # Route to next stage
        # Track history

    def reject_cr(cr_id, stage, rejection_reason):
        # Mark CR as rejected
        # Reset to draft
        # Notify creator
```

**deployment_service.py (400 lines)**
```python
class DeploymentManager:
    def pre_deployment_checks(cr_id):
        # Syntax validation
        # Security scanning
        # Performance analysis
        # Compatibility check

    def deploy_cr(cr_id, environment):
        # Execute deployment
        # Track execution time
        # Validate success

    def post_deployment_validation(cr_id):
        # Run test suite
        # Validate data integrity
        # Check performance metrics

    def rollback_deployment(cr_id, reason):
        # Revert changes
        # Restore previous version
        # Validate rollback
```

---

### 3. Backend API Routes (dbmgmt_phase4.py - 700 lines)

**Endpoints:**
```
POST /cr/create
  ├─ Create change request
  └─ Body: {finding_id, optimization_id, title, description, priority}

GET /cr/{cr_id}
  ├─ Get CR details with full workflow
  └─ Returns: {CR, approvals, deployments, audit_log}

POST /cr/{cr_id}/submit
  ├─ Submit for approval
  └─ Triggers routing to first approver

POST /cr/{cr_id}/approve
  ├─ Approve at current stage
  ├─ Body: {stage, comment}
  └─ Routes to next stage or deployment

POST /cr/{cr_id}/reject
  ├─ Reject CR
  ├─ Body: {stage, reason}
  └─ Resets to draft

GET /cr/list
  ├─ List all CRs
  ├─ Filters: status, priority, assigned_to, date_range
  └─ Pagination: limit=50

POST /deployment/{cr_id}/pre-checks
  ├─ Run pre-deployment validation
  └─ Returns: {checks_passed, warnings, errors}

POST /deployment/{cr_id}/execute
  ├─ Execute deployment
  ├─ Body: {environment: staging|production}
  └─ Returns: {deployment_id, status, duration}

POST /deployment/{cr_id}/validate
  ├─ Run post-deployment tests
  └─ Returns: {all_passed, failed_tests}

POST /deployment/{cr_id}/rollback
  ├─ Rollback deployment
  ├─ Body: {reason}
  └─ Returns: {rollback_status}

GET /audit/cr/{cr_id}
  ├─ Full audit trail
  └─ Returns: {events_timeline}

GET /database/versions/{db_id}
  ├─ Database version history
  └─ Returns: {versions_list, current_version}
```

---

### 4. Frontend Components (Phase4Pages.tsx - 800 lines)

**ChangeRequestPage:**
- CR dashboard with filters
- Create CR form (linked to finding/optimization)
- CR detail view with approval stages
- Approval interface for reviewers
- Comments/discussion thread
- Deployment tracking

**DeploymentDashboard:**
- Pre-deployment checks UI
- Deploy button with environment selector
- Real-time deployment progress
- Post-deployment validation results
- Rollback controls
- Deployment history

---

### 5. Unit Tests (test_dbmgmt_phase4.py - 600 lines)

**Test Classes:**
- TestChangeRequestCreation (8 tests)
- TestChangeRequestWorkflow (12 tests)
- TestApprovalRouting (8 tests)
- TestPreDeploymentChecks (10 tests)
- TestDeployment (12 tests)
- TestPostDeploymentValidation (8 tests)
- TestRollback (6 tests)
- TestAuditLogging (6 tests)

**Total: 70 test cases**

---

## Implementation Timeline (10 Days)

**Days 1-2:** Database & Services
- Migration script
- Change request service
- Deployment service

**Days 3-4:** Backend API
- CR management endpoints
- Deployment endpoints
- Approval routing

**Days 5:** Frontend
- CR dashboard
- Deployment interface
- Approval UI

**Days 6-7:** Integration & Workflow Testing
- Multi-stage approval flow
- Deployment to staging
- Rollback functionality

**Days 8-9:** Refinement
- Error handling
- Edge cases
- 70 unit tests

**Day 10:** Staging & Sign-Off

---

**Version:** 1.0
**Status:** Ready for Implementation
