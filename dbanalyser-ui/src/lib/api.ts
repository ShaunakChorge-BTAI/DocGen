import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
})

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url: string = err.config?.url || ''
    const isAuthCall = url.includes('/auth/token') || url.includes('/auth/register') || url.includes('/auth/me')
    // Only auto-redirect on 401 for protected API calls, never for auth endpoints themselves
    if (err.response?.status === 401 && !isAuthCall) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  // Backend expects JSON body: { username, password }
  login: (username: string, password: string) =>
    api.post('/auth/token', { username, password }),
  // Register creates org + first admin user
  register: (org_name: string, username: string, email: string, password: string) =>
    api.post('/auth/register', { org_name, username, email, password }),
  // GET /auth/me — returns { username, email, role } or { username:"anonymous" } when auth disabled
  me: () => api.get('/auth/me'),
}

// ── Databases ─────────────────────────────────────────────────────────────────
// GET /databases → DB[]  (plain list)
// DB fields: id, name, environment, host, port, database_name, is_active, last_run_at, last_health
export const dbApi = {
  list:    (activeOnly?: boolean) => api.get<any[]>('/databases', { params: activeOnly ? { active_only: true } : {} }),
  get:     (name: string)         => api.get<any>(`/databases/${name}`),
  summary: ()                      => api.get('/databases/summary'),
}

// ── Runs ─────────────────────────────────────────────────────────────────────
// GET /runs → { runs: Run[] }
// Run fields: id, run_id, label, db_name, health_score, total_objects, total_issues,
//             critical_count, high_count, medium_count, low_count, status, timestamp, duration_sec
export const runApi = {
  list:    (dbName?: string) => api.get<{ runs: any[] }>('/runs', { params: dbName ? { db_name: dbName } : {} }),
  get:     (id: number)      => api.get<any>(`/runs/${id}`),
  trigger: (body: any)       => api.post('/runs/trigger', body),
}

// ── Findings ─────────────────────────────────────────────────────────────────
// GET /findings/run/{run_id} → { findings: Finding[], total, run_id }
// GET /findings/summary/{run_id} → { run_id, critical, high, medium, low, total }
// Finding fields: id, run_id, rule_id, category, severity, object_name, object_type,
//                 schema_name, issue, recommendation, line_number, snippet, status
export const findingsApi = {
  byRun:   (runId: number, params?: Record<string, any>) =>
    api.get<{ findings: any[]; total: number }>('/findings/', { params: { run_id: runId, limit: 5000, ...params } }),
  summary: (runId: number)               => api.get<any>(`/findings/summary/${runId}`),
}

// ── Trend ─────────────────────────────────────────────────────────────────────
export const trendApi = {
  all:    () => api.get('/trend/all'),
  byDb:   (dbName: string) => api.get(`/trend/${dbName}`),
}

// ── Schedules ─────────────────────────────────────────────────────────────────
// GET  /schedules              → Schedule[]
// POST /schedules              → Schedule  (create or update, keyed by db_name)
// DELETE /schedules/{id}       → OkResponse
// PATCH /schedules/{id}/toggle → OkResponse  (body: ?enabled=true)
// POST /schedules/{id}/trigger → JobStatusResponse
export const schedulesApi = {
  list:    ()                           => api.get<any[]>('/schedules'),
  upsert:  (body: any)                  => api.post<any>('/schedules', body),
  remove:  (id: number)                 => api.delete(`/schedules/${id}`),
  toggle:  (id: number, enabled: boolean) =>
    api.patch(`/schedules/${id}/toggle`, null, { params: { enabled } }),
  trigger: (id: number)                 => api.post<any>(`/schedules/${id}/trigger`),
}

// ── Schema ─────────────────────────────────────────────────────────────────────
// POST /schema/search → { query, results: SchemaSearchResult[], total }
// SchemaSearchResult fields: object_type, schema_name, object_name, parent_name, definition, similarity_score
export const schemaApi = {
  search: (query: string, db_id?: number) =>
    api.post<{ results: any[]; total: number; query: string }>('/schema/search', {
      query,
      top_k: 20,
      min_score: 0.0,
      object_types: ['procedure', 'view', 'function'],
      ...(db_id && { db_registry_id: db_id }),
    }),
  get: (schema: string, name: string) =>
    api.get<any>(`/schema/${schema}/${name}`),
  listObjects: (dbName: string, runId?: number, objectType?: string) =>
    api.get<any[]>('/schema/objects', {
      params: {
        ...(dbName && { db_name: dbName }),
        ...(runId && { run_id: runId }),
        ...(objectType && { object_type: objectType }),
      },
    }),
  getDependencies: (tableName: string, dbName?: string) =>
    api.get<any[]>(`/schema/dependencies`, {
      params: {
        ...(tableName && { table_name: tableName }),
        ...(dbName && { db_name: dbName }),
      },
    }),
}

// ── Metadata ────────────────────────────────────────────────────────────────────
// POST /metadata/{db_name}/refresh → OkResponse (async metadata fetch)
// GET /metadata/{db_name} → { db_name, last_updated, objects: { Table, Procedure, View, Index } }
export const metadataApi = {
  refresh: (dbName: string) =>
    api.post<any>(`/metadata/${dbName}/refresh`),
  get: (dbName: string, objectType?: string) =>
    api.get<any>(`/metadata/${dbName}`, {
      params: objectType ? { object_type: objectType } : {},
    }),
}

// ── Live Metrics ────────────────────────────────────────────────────────────────
// POST /live-metrics/{db_name}/scan → OkResponse (capture real-time metrics)
// GET /live-metrics/{run_id}/{metric_type} → { run_id, metric_type, metrics[], total }
// GET /live-metrics/{db_name}/live-status → { blocking_sessions, slow_queries, largest_tables }
export const liveMetricsApi = {
  scan: (dbName: string, metricTypes?: string[]) =>
    api.post<any>(`/live-metrics/${dbName}/scan`, { metric_types: metricTypes }),
  getMetric: (runId: number, metricType: string) =>
    api.get<any>(`/live-metrics/${runId}/${metricType}`),
  getLiveStatus: (dbName: string) =>
    api.get<any>(`/live-metrics/${dbName}/live-status`),
}
