# Phase 1 Deployment Guide
## Complete Instructions for Phase 1 Implementation

**Last Updated:** 2026-04-08
**Status:** Ready for Deployment
**Duration:** 10 working days

---

## Quick Start (5 Minutes)

```bash
# 1. Backup PostgreSQL
pg_dump -U postgres dbanalyser > backup_phase1_$(date +%Y%m%d).sql

# 2. Run migration
psql -U postgres -d dbanalyser -f dbanalyser/migrations/001_phase1_schema.sql

# 3. Verify
psql -U postgres -d dbanalyser -c "SELECT COUNT(*) FROM schema_objects;"
# Expected: 1531

# 4. Add API routes
# Copy findings_phase1.py content to dbanalyser/api/routes/

# 5. Add React components
# Copy AnalysisPage_Phase1.tsx to dbanalyser-ui/src/pages/

# 6. Run tests
pytest dbanalyser/tests/test_findings_phase1.py -v

# 7. Start services
# Backend: python -m dbanalyser api
# Frontend: npm start
```

---

## Step-by-Step Deployment

### Step 1: Database Migration (30 minutes)

```bash
# 1.1 Backup existing database
cd D:\LTFS\ltfs-analyzer
pg_dump -U postgres dbanalyser > backup_phase1_$(date +%Y%m%d).sql
echo "Backup created"

# 1.2 Run migration
psql -U postgres -d dbanalyser -f dbanalyser/migrations/001_phase1_schema.sql

# 1.3 Verify tables created
psql -U postgres -d dbanalyser << 'EOF'
\dt finding_status_history
\dt schema_object_versions
\dt finding_comments
\dt metadata_sync_jobs
EOF

# 1.4 Verify indexes
psql -U postgres -d dbanalyser -c "SELECT indexname FROM pg_indexes WHERE tablename='findings';"

# Expected output (6 indexes):
# idx_findings_run_id
# idx_findings_rule_id
# idx_findings_status
# idx_findings_severity
# idx_findings_assigned_to
# idx_findings_run_severity
```

**Success Indicators:**
- ✅ All 4 new tables exist
- ✅ All indexes created
- ✅ 1531 objects in schema_objects
- ✅ 1531 versions in schema_object_versions

### Step 2: Backend API Setup (20 minutes)

```bash
# 2.1 Copy API file
cp dbanalyser/api/routes/findings_phase1.py dbanalyser/api/routes/findings.py

# 2.2 Update __init__.py to import new routes
# Add to dbanalyser/api/__init__.py:
# from .routes.findings import router as findings_router
# app.include_router(findings_router)

# 2.3 Install any new dependencies
pip install -r requirements.txt

# 2.4 Test API locally
python -m uvicorn dbanalyser.api.main:app --reload --port 8000

# 2.5 Verify endpoints in browser
# GET http://localhost:8000/api/findings?limit=10&offset=0
# Should return JSON with findings
```

**Success Indicators:**
- ✅ API starts without errors
- ✅ GET /findings returns paginated results
- ✅ GET /findings/{id} returns full detail
- ✅ PATCH /findings/{id}/status works
- ✅ POST /findings/{id}/comments works

### Step 3: Frontend Setup (20 minutes)

```bash
# 3.1 Copy React component
cp dbanalyser-ui/src/pages/AnalysisPage_Phase1.tsx dbanalyser-ui/src/pages/AnalysisPage.tsx

# 3.2 Update router (if needed)
# In src/App.tsx or src/Router.tsx, import AnalysisPage

# 3.3 Install dependencies
npm install @tanstack/react-query axios

# 3.4 Start development server
cd dbanalyser-ui
npm start

# 3.5 Test in browser
# http://localhost:5173
# Should show Analysis page with run selector and findings table
```

**Success Indicators:**
- ✅ React app starts without errors
- ✅ Analysis page loads
- ✅ Run dropdown shows runs
- ✅ Finding table displays (if data exists)
- ✅ Pagination works
- ✅ Finding detail modal opens

### Step 4: Integration Testing (20 minutes)

```bash
# 4.1 Run unit tests
pytest dbanalyser/tests/test_findings_phase1.py -v

# Expected output:
# test_list_findings_with_pagination PASSED
# test_list_findings_filter_by_severity PASSED
# test_get_finding_detail_success PASSED
# test_update_finding_status_valid PASSED
# test_add_comment_success PASSED
# ... (all tests pass)

# 4.2 Manual E2E test
# 1. Load http://localhost:5173/analysis
# 2. Select a run
# 3. See findings displayed
# 4. Click "View" on a finding
# 5. Modal opens with full details
# 6. Change status
# 7. Add comment
# 8. Verify history shows changes
```

**Success Indicators:**
- ✅ All unit tests pass
- ✅ E2E workflow completes
- ✅ No console errors
- ✅ Status changes persist
- ✅ Comments appear immediately

### Step 5: Staging Deployment (30 minutes)

```bash
# 5.1 Deploy to staging environment
# (Your CI/CD process here)
# Example:
git add .
git commit -m "[PHASE1] Complete Phase 1 implementation"
git push origin feature/phase-1-foundation

# 5.2 Run staging tests
# kubectl apply -f k8s/staging.yaml
# OR
# docker-compose -f docker-compose.staging.yml up

# 5.3 Verify in staging
curl http://staging.dbanalyser.internal/api/findings?limit=5

# 5.4 Smoke test
# - Load dashboard
# - Create new finding status
# - Add comment
# - Verify all working

# 5.5 Performance test
# - Load with 1000 findings
# - Check response time <200ms
# - Check memory usage stable
```

**Success Indicators:**
- ✅ Staging deployment successful
- ✅ All endpoints respond
- ✅ Database migrated
- ✅ Frontend loads correctly
- ✅ Performance acceptable

---

## Files Created / Modified

### Database

**Created:**
- `dbanalyser/migrations/001_phase1_schema.sql` - Migration script

**Modified:**
- `findings` table - Added status, comments, assignment columns

**New Tables:**
- `schema_objects` (recreated, now with TEXT definition)
- `schema_object_versions` (new)
- `finding_status_history` (new)
- `finding_comments` (new)
- `metadata_sync_jobs` (new)

### Backend

**Created:**
- `dbanalyser/api/routes/findings_phase1.py` - API endpoints
- `dbanalyser/tests/test_findings_phase1.py` - Unit tests

**Modified (if needed):**
- `dbanalyser/api/__init__.py` - Register findings routes
- `dbanalyser/db/models.py` - Add new model classes

### Frontend

**Created:**
- `dbanalyser-ui/src/pages/AnalysisPage_Phase1.tsx` - Analysis dashboard
- (Components: FindingDetailModal)

**Modified (if needed):**
- `src/App.tsx` - Import AnalysisPage
- `src/Router.tsx` - Add route

---

## Rollback Procedure

### If Database Migration Fails

```bash
# Step 1: Restore from backup
psql -U postgres dbanalyser < backup_phase1_YYYYMMDD.sql

# Step 2: Verify restore
psql -U postgres -d dbanalyser -c "SELECT COUNT(*) FROM schema_objects;"
# Should be 1531

# Step 3: Verify old schema intact
psql -U postgres -d dbanalyser -c "\dt schema_objects"
```

### If API Deployment Fails

```bash
# Step 1: Revert git changes
git revert HEAD

# Step 2: Redeploy previous version
git checkout main
python -m dbanalyser api

# Step 3: Verify
curl http://localhost:8000/api/findings?limit=1
```

### If Frontend Deployment Fails

```bash
# Step 1: Revert changes
git revert HEAD

# Step 2: Rebuild
npm install
npm run build

# Step 3: Restart
npm start
```

---

## Verification Checklist

### Database Layer
- [ ] Migration ran without errors
- [ ] All 4 new tables created
- [ ] All 12 indexes created
- [ ] 1531 objects in schema_objects (full definition stored)
- [ ] 1531 versions in schema_object_versions
- [ ] Backup verified

### API Layer
- [ ] GET /findings returns paginated results
- [ ] Limit/offset working (max 500)
- [ ] Filters working (severity, status, rule_id)
- [ ] GET /findings/{id} returns full detail with schema_object
- [ ] PATCH /findings/{id}/status creates history record
- [ ] POST /findings/{id}/comments adds comment
- [ ] GET /findings/{id}/history returns timeline
- [ ] All endpoints require auth
- [ ] Error handling working
- [ ] Performance <100ms per query

### Frontend Layer
- [ ] AnalysisPage loads without errors
- [ ] Run dropdown shows all runs
- [ ] Filters work (severity, status)
- [ ] Pagination works (next, previous)
- [ ] Finding table displays results
- [ ] Finding detail modal opens
- [ ] 5 tabs render (problem, solution, help, comments, history)
- [ ] Status change works
- [ ] Comment addition works
- [ ] History timeline displays
- [ ] No console errors
- [ ] Mobile responsive

### Integration
- [ ] E2E workflow completes (view → detail → status → comment)
- [ ] Staging deployment successful
- [ ] Load test (1000 findings) passes
- [ ] Performance acceptable

---

## Troubleshooting

### Database Issues

**Problem: Migration fails with "table already exists"**
```sql
-- Solution: Drop and recreate
DROP TABLE schema_objects CASCADE;
-- Then run migration again
```

**Problem: Index creation fails**
```sql
-- Solution: Check if index exists first
SELECT * FROM pg_indexes WHERE indexname = 'idx_findings_run_id';
-- Drop if exists, recreate manually
```

### API Issues

**Problem: "Finding not found" (404)**
- Verify finding.id exists in database
- Check query filter is correct
- Ensure org_id matches current user

**Problem: Slow queries**
- Verify indexes created: `SELECT * FROM pg_indexes`
- Check query plan: `EXPLAIN ANALYZE SELECT...`
- Consider query optimization

### Frontend Issues

**Problem: "Cannot read property 'data'"**
- Verify API returns correct format
- Check API response in Network tab
- Ensure mock data exists if testing offline

**Problem: Modal doesn't open**
- Verify finding_id is passed correctly
- Check console for JavaScript errors
- Verify API endpoint accessible

---

## Performance Targets

| Operation | Target | Acceptable |
|-----------|--------|-----------|
| List findings (50 items) | <100ms | <200ms |
| Get finding detail | <50ms | <100ms |
| Update status | <100ms | <200ms |
| Add comment | <100ms | <200ms |
| Frontend page load | <2s | <3s |
| Modal open | <500ms | <1000ms |

---

## Monitoring & Logs

### What to Monitor

```
Backend:
  - API response times (target <100ms)
  - Database query times
  - Error rates
  - Authentication failures

Database:
  - Slow queries log
  - Index usage
  - Table sizes
  - Lock contention

Frontend:
  - Console errors
  - Network requests
  - Load time
  - Memory usage
```

### Log Locations

```
Backend logs:
  - /var/log/dbanalyser/api.log
  - PostgreSQL: /var/log/postgresql/postgresql.log

Frontend:
  - Browser console (F12)
  - Network tab (API requests)

System:
  - docker logs
  - journalctl -u dbanalyser
```

---

## Sign-Off

**Phase 1 Deployment Complete When:**
- ✅ All verification checklist items pass
- ✅ No critical issues found
- ✅ Performance targets met
- ✅ Team sign-off obtained

**Sign-offs Required:**
- [ ] Database Lead: Migration successful
- [ ] Backend Lead: API functional
- [ ] Frontend Lead: UI responsive
- [ ] QA Lead: Testing complete
- [ ] Product Owner: Features working as specified

---

## Next Phase

After Phase 1 sign-off, proceed to Phase 2:
- SQL Optimizer integration
- Ollama local setup
- Impact analysis
- Download functionality

**Phase 2 Start Date:** [After Phase 1 approval]
**Phase 2 Duration:** 2 weeks (10 working days)

---

## Support

**During Deployment:**
- Slack: #dbanalyser-phase1
- Daily Standup: 9:30 AM
- Escalation: [Lead name]

**After Deployment:**
- Documentation: [Wiki link]
- API Docs: [Swagger link]
- Support: [Support email]

---

**Ready to Deploy?** Follow the Quick Start section above. ✅
