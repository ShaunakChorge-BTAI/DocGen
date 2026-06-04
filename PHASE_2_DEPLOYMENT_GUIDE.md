# Phase 2 Deployment Guide
## SQL Optimizer with Local Ollama Integration

**Last Updated:** 2026-04-08
**Status:** Ready for Deployment
**Duration:** 10 working days

---

## Prerequisites

### System Requirements
- PostgreSQL database (UAT + Production)
- Python 3.9+
- Node.js 16+
- Ollama installed locally

### Ollama Setup
```bash
# 1. Download Ollama
# Windows: https://ollama.ai/download
# Mac: https://ollama.ai/download
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull a model (choose one)
ollama pull mistral        # Recommended (7GB) - best SQL optimization
ollama pull neural-chat    # Smaller (5GB) - faster responses
ollama pull dolphin-mixtral # Excellent (27GB) - if you have resources

# 3. Start Ollama service
ollama serve               # Runs on localhost:11434

# 4. Verify in another terminal
curl http://localhost:11434/api/tags
```

---

## Deployment Steps

### Step 1: Database Migration (30 minutes)

```bash
cd D:\LTFS\ltfs-analyzer

# Backup current database
pg_dump -U postgres dbanalyser > backup_phase2_$(date +%Y%m%d).sql

# Run Phase 2 migration
psql -U postgres -d dbanalyser -f dbanalyser/migrations/002_phase2_optimizer_schema.sql

# Verify tables created
psql -U postgres -d dbanalyser << 'EOF'
SELECT table_name FROM information_schema.tables
WHERE table_name IN (
  'schema_object_optimizations',
  'optimization_attempts',
  'optimization_metrics',
  'optimization_query_plans',
  'optimization_change_requests'
);
EOF

# Expected output: 5 tables
```

**Success Indicators:**
- ✅ All 5 new tables exist
- ✅ All 9 indexes created
- ✅ View `v_optimization_summary` created

### Step 2: Backend Services (20 minutes)

```bash
# Copy service files
cp dbanalyser/services/ollama_service.py dbanalyser/services/
cp dbanalyser/services/optimization_db_utils.py dbanalyser/services/

# Install new dependencies
pip install ollama httpx  # For Ollama integration
pip install pandas numpy  # For metrics

# Verify imports
python -c "from dbanalyser.services.ollama_service import OllamaOptimizer; print('✅ Ollama service loaded')"
python -c "from dbanalyser.services.optimization_db_utils import execute_on_database; print('✅ DB utils loaded')"
```

### Step 3: API Routes (20 minutes)

```bash
# Copy API routes
cp dbanalyser/api/routes/optimizer_phase2.py dbanalyser/api/routes/optimizer.py

# Update dbanalyser/api/main.py to include optimizer routes
# Add these lines after other route imports:
from dbanalyser.api.routes import optimizer as optimizer_routes

# Add this line after other include_router calls:
app.include_router(optimizer_routes.router)

# Test API startup
python -m uvicorn dbanalyser.api.main:app --reload --port 8000

# In another terminal, test optimizer health endpoint
curl http://localhost:8000/api/optimizer/health
```

**Expected Response:**
```json
{
  "ollama_available": true,
  "models": ["mistral"],
  "model_loaded": true
}
```

### Step 4: Frontend (20 minutes)

```bash
# Copy React component
cp dbanalyser-ui/src/pages/OptimizerPage_Phase2.tsx dbanalyser-ui/src/pages/OptimizerPage.tsx

# Install frontend dependencies
cd dbanalyser-ui
npm install react-syntax-highlighter@^15.x

# Update router to include optimizer
# Edit src/App.tsx or src/Router.tsx to add:
import OptimizerPage from './pages/OptimizerPage'
// In route config:
{ path: '/optimizer', element: <OptimizerPage /> }

# Start frontend
npm run dev

# Test in browser: http://localhost:5173/optimizer
```

### Step 5: Testing (20 minutes)

```bash
# Run unit tests
pytest dbanalyser/tests/test_optimizer_phase2.py -v

# Expected: All tests pass
# Run specific test class:
pytest dbanalyser/tests/test_optimizer_phase2.py::TestOptimizerSuggest -v
pytest dbanalyser/tests/test_optimizer_phase2.py::TestOptimizerTest -v
```

### Step 6: Integration Testing (20 minutes)

**Manual E2E Workflow:**

1. ✅ **Health Check**
   ```bash
   curl http://localhost:8000/api/optimizer/health
   # Should show ollama_available: true
   ```

2. ✅ **Get Optimization Suggestion**
   ```bash
   curl -X POST http://localhost:8000/api/optimizer/suggest \
     -H "Content-Type: application/json" \
     -d '{
       "finding_id": 1,
       "sql_code": "SELECT * FROM users WHERE id = 1",
       "object_type": "Procedure",
       "rule_id": "PERF001",
       "issue_description": "SELECT * issue"
     }'
   # Should return suggestion with confidence score
   ```

3. ✅ **Test on UAT Database**
   ```bash
   curl -X POST http://localhost:8000/api/optimizer/test \
     -H "Content-Type: application/json" \
     -d '{
       "optimization_id": 1
     }'
   # Should return comparison metrics
   ```

4. ✅ **Download Optimized SQL**
   - Open http://localhost:5173/optimizer
   - Get suggestion → Click "Download"
   - Verify .sql file downloads with both original + optimized

5. ✅ **Submit Change Request**
   - From optimizer UI, click "Submit CR"
   - Fill in CR details
   - Verify CR record created in database

6. ✅ **Check History**
   ```bash
   curl http://localhost:8000/api/optimizer/history/1
   # Should show all attempts for finding 1
   ```

---

## Verification Checklist

### Database Layer
- [ ] Migration ran without errors
- [ ] All 5 new tables exist
- [ ] All 9 indexes created
- [ ] View `v_optimization_summary` works
- [ ] Backup verified

### Ollama Setup
- [ ] Ollama installed
- [ ] Model pulled (mistral/neural-chat)
- [ ] Ollama service running
- [ ] API responds on localhost:11434

### Backend API
- [ ] GET /optimizer/health returns available: true
- [ ] POST /optimizer/suggest returns suggestion
- [ ] POST /optimizer/test runs UAT tests
- [ ] GET /optimizer/history returns attempts
- [ ] POST /optimizer/download returns SQL
- [ ] POST /optimizer/submit-cr creates CR
- [ ] GET /optimizer/suggestions lists optimizations
- [ ] All endpoints require auth
- [ ] Performance <15s for suggestion, <10s for test

### Frontend
- [ ] OptimizerPage loads
- [ ] Tab navigation works (Suggest, Test, History, CR)
- [ ] Can input SQL and get suggestion
- [ ] Test results display metrics
- [ ] Download button works
- [ ] CR form submits
- [ ] No console errors
- [ ] Mobile responsive

### Integration
- [ ] E2E workflow: Suggest → Test → Download → CR
- [ ] Ollama response time acceptable
- [ ] UAT database tests accurate
- [ ] Data integrity verified
- [ ] CR workflow functional

---

## Configuration

### Ollama Model Selection

| Model | Size | Speed | Quality | SQL Focus |
|-------|------|-------|---------|-----------|
| mistral | 7GB | Medium | Good | Good |
| neural-chat | 5GB | Fast | Medium | Medium |
| dolphin-mixtral | 27GB | Slow | Excellent | Excellent |

**Recommendation:** Start with `mistral` (good balance)

### Environment Variables

```bash
# .env or analysis_config.yaml
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=30          # seconds
UAT_DATABASE=dbanalyser    # Your UAT database name
QUERY_TIMEOUT=30           # seconds for UAT queries
```

---

## Troubleshooting

### Ollama Not Available

```
Error: Failed to connect to Ollama

Solution:
1. Check Ollama is running: ollama serve
2. Check port: curl localhost:11434/api/tags
3. Check model is pulled: ollama pull mistral
4. Check firewall allows localhost:11434
```

### Query Timeout on UAT

```
Error: Query timeout after 30 seconds

Solution:
1. Increase timeout: QUERY_TIMEOUT=60
2. Optimize UAT indexes
3. Check UAT database load
4. Consider breaking large queries
```

### Slow Ollama Responses

```
Error: Ollama takes >30 seconds

Solution:
1. Check Ollama process: ps aux | grep ollama
2. Try smaller model: neural-chat
3. Restart Ollama: killall ollama; ollama serve
4. Check system memory: free -h
```

### Data Integrity Failures

```
Error: Optimized query returns different rows

Solution:
1. Verify optimization is correct
2. Check WHERE clause and JOINs
3. Review original vs optimized in UI
4. Manually test SQL on UAT
5. Reject optimization, try again
```

---

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Ollama suggestion | <15s | 8-12s |
| UAT test | <10s | 2-8s |
| API response | <100ms | 50-80ms |
| Frontend load | <2s | 1.2s |
| Modal open | <500ms | 200ms |
| Download | <2s | 500ms |

---

## Rollback Procedure

### If Entire Phase 2 Fails

```bash
# 1. Restore database backup
psql -U postgres -d dbanalyser < backup_phase2_YYYYMMDD.sql

# 2. Revert API changes
git revert HEAD  # Removes optimizer routes

# 3. Revert frontend changes
git revert HEAD  # Removes OptimizerPage

# 4. Restart services
python -m dbanalyser api
npm start
```

### If Just Ollama Integration Fails

```bash
# The UI will show "Ollama Not Available"
# Users can:
1. Install Ollama locally
2. Use a different machine for Ollama
3. Revert to Phase 1 (no optimizer)

# No database rollback needed
```

---

## Post-Deployment

### Day 1 Tasks
- [ ] Verify all tests pass
- [ ] Monitor API performance
- [ ] Monitor Ollama memory/CPU
- [ ] Gather user feedback

### Week 1 Tasks
- [ ] Optimize Ollama prompts based on suggestions
- [ ] Fine-tune timeout values
- [ ] Review change requests submitted

### Week 2+ Tasks
- [ ] Implement Phase 3 (Reports + Help System)
- [ ] Add more Ollama models for A/B testing
- [ ] Implement advanced metrics tracking

---

## Support

**During Deployment:**
- Slack: #dbanalyser-phase2
- Daily Standup: 9:30 AM
- Escalation: [Lead name]

**After Deployment:**
- API Docs: http://localhost:8000/docs
- Status: http://localhost:8000/api/optimizer/health
- Logs: Check application logs and Ollama console

---

## Success Criteria

### Phase 2 is Complete When:
- ✅ Database migration successful
- ✅ Ollama integration functional
- ✅ All 8 API endpoints working
- ✅ Frontend UI complete
- ✅ 25+ unit tests passing
- ✅ E2E workflow tested
- ✅ Performance targets met
- ✅ Team sign-off obtained

---

**Ready to Deploy?** Follow the steps above. Start with Prerequisites, then Step 1-6 in order.

**Estimated Time:** 2 hours (with Ollama already downloaded)
