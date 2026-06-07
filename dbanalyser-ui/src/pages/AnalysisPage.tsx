import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { runApi, findingsApi, dbApi, api } from '../lib/api'
import PageHeader from '../components/PageHeader'

export default function AnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDb, setSelectedDb] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [filters, setFilters] = useState({
    severity: null,
    status: '',
    rule_id: null
  })
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 })
  const [selectedFinding, setSelectedFinding] = useState(null)
  const [detailModalOpen, setDetailModalOpen] = useState(false)

  // Fetch all databases for dropdown
  const { data: dbsData } = useQuery({
    queryKey: ['databases'],
    queryFn: () => dbApi.list().then(r => r.data),
  })
  const databases: any[] = dbsData ?? []

  // Fetch runs — filter by selected database if provided
  const { data: runsData } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn: () => runApi.list(selectedDb || undefined).then(r => r.data.runs || [])
  })
  const runs = runsData ?? []

  // Auto-select run from URL or latest run
  useEffect(() => {
    const urlRunId = searchParams.get('run_id')
    if (urlRunId) {
      const id = parseInt(urlRunId, 10)
      if (!isNaN(id) && selectedRun !== id) {
        setSelectedRun(id)
        // Optionally update selectedDb if we can infer it, but user can select.
        // Clear the URL param
        searchParams.delete('run_id')
        setSearchParams(searchParams, { replace: true })
      }
    } else if (runs.length > 0 && selectedRun === null) {
      setSelectedRun(runs[0].id)
    }
  }, [runs.length, searchParams, selectedRun, setSearchParams])

  // When database changes, reset selected run to latest for that db (or null if none)
  useEffect(() => {
    // Only reset if we didn't just load from URL
    if (selectedDb && runs.length > 0 && selectedRun !== runs[0].id) {
      setSelectedRun(runs[0].id)
    } else if (!selectedDb && !selectedRun) {
      setSelectedRun(null)
    }
    setPagination({ limit: 50, offset: 0 })
  }, [selectedDb, runs])

  // Fetch findings with filters and pagination — API returns { findings: Finding[], total }
  const { data: findingsData, isLoading } = useQuery({
    queryKey: ['findings', selectedRun, filters, pagination],
    queryFn:  () => findingsApi.byRun(selectedRun!, {
      ...(filters.severity ? { severity: filters.severity } : {}),
      ...(filters.status   ? { status:   filters.status   } : {}),
      limit:  pagination.limit,
      offset: pagination.offset,
    }).then(r => r.data),
    enabled: !!selectedRun
  })

  // Safely unpack findings data — handle both wrapped and unwrapped formats
  const findings = Array.isArray(findingsData?.findings)
    ? findingsData.findings
    : Array.isArray(findingsData?.data)
    ? findingsData.data
    : []
  const total = findingsData?.total ?? 0

  return (
    <div className="p-6">
      <PageHeader
        title="Analysis"
        subtitle="Review findings from database assessment"
      />

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex gap-4 items-end mb-4">
          {/* Database Selector */}
          <div className="flex-1">
            <label className="text-sm font-medium text-gray-700 block mb-1">
              Select Database
            </label>
            <select
              value={selectedDb ?? ''}
              onChange={(e) => {
                const dbName = e.target.value || null
                setSelectedDb(dbName)
              }}
              className="w-full border rounded-lg px-3 py-2"
            >
              <option value="">All Databases</option>
              {databases.length === 0 ? (
                <option disabled>No databases found</option>
              ) : (
                databases.map(db => (
                  <option key={db.id} value={db.name}>
                    {db.name}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Run Selector */}
          <div className="flex-1">
            <label className="text-sm font-medium text-gray-700 block mb-1">
              Select Run
            </label>
            <select
              value={selectedRun ?? ''}
              onChange={(e) => {
                const newRunId = e.target.value ? parseInt(e.target.value) : null
                setSelectedRun(newRunId)
                setPagination({ limit: 50, offset: 0 })
              }}
              className="w-full border rounded-lg px-3 py-2"
            >
              <option value="">Choose a run...</option>
              {runs.length === 0 ? (
                <option disabled>{selectedDb ? 'No runs found for this database' : 'No runs available'}</option>
              ) : (
                runs.map(run => (
                  <option key={run.id} value={run.id}>
                    Run #{run.id} - {run.label} ({run.total_issues} findings)
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              Severity
            </label>
            <select
              value={filters.severity || ''}
              onChange={(e) => {
                setFilters({ ...filters, severity: e.target.value || null })
                setPagination({ limit: 50, offset: 0 })
              }}
              className="border rounded-lg px-3 py-2"
            >
              <option value="">All</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              Status
            </label>
            <select
              value={filters.status || ''}
              onChange={(e) => {
                setFilters({ ...filters, status: e.target.value || null })
                setPagination({ limit: 50, offset: 0 })
              }}
              className="border rounded-lg px-3 py-2"
            >
              <option value="">All</option>
              <option value="Open">Open</option>
              <option value="Pending">Pending</option>
              <option value="In Progress">In Progress</option>
              <option value="Optimized">Optimized</option>
              <option value="CR_Submitted">CR Submitted</option>
              <option value="Acknowledged">Acknowledged</option>
            </select>
          </div>
        </div>
      </div>

      {/* Findings Table */}
      {!selectedRun ? (
        <div className="bg-amber-50 rounded-lg p-6 text-center text-amber-800">
          Select a run to view findings
        </div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            {isLoading ? (
              <div className="p-6 text-center text-gray-500">Loading findings...</div>
            ) : findings.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                {isLoading ? 'Loading findings...' : 'No findings found for this run'}
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Severity</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Rule</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Object</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Type</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Priority</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {findings.map((finding) => (
                    <tr key={finding.id} className="hover:bg-gray-50">
                      <td className="px-6 py-3 text-sm">
                        <span className={`px-2 py-1 rounded text-white text-xs ${
                          finding.severity === 'Critical' ? 'bg-red-600' :
                          finding.severity === 'High' ? 'bg-orange-600' :
                          finding.severity === 'Medium' ? 'bg-yellow-600' :
                          'bg-blue-600'
                        }`}>
                          {finding.severity}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-sm font-mono text-gray-900">{finding.rule_id}</td>
                      <td className="px-6 py-3 text-sm text-gray-900">{finding.object_name}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{finding.object_type}</td>
                      <td className="px-6 py-3 text-sm">
                        <span className={`px-2 py-1 rounded text-xs ${
                          finding.status === 'Open' ? 'bg-cyan-100 text-cyan-700' :
                          finding.status === 'Pending' ? 'bg-blue-100 text-blue-700' :
                          finding.status === 'In Progress' ? 'bg-yellow-100 text-yellow-700' :
                          finding.status === 'Optimized' ? 'bg-green-100 text-green-700' :
                          finding.status === 'Acknowledged' ? 'bg-purple-100 text-purple-700' :
                          finding.status === 'CR_Submitted' ? 'bg-orange-100 text-orange-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {finding.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-900">{finding.priority}</td>
                      <td className="px-6 py-3 text-sm">
                        <button
                          onClick={() => {
                            setSelectedFinding(finding)
                            setDetailModalOpen(true)
                          }}
                          className="text-blue-600 hover:text-blue-900 font-medium"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          <div className="mt-6 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Showing {pagination.offset + 1} to{' '}
              {Math.min(pagination.offset + pagination.limit, total)} of {total}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() =>
                  setPagination({
                    ...pagination,
                    offset: Math.max(0, pagination.offset - pagination.limit)
                  })
                }
                disabled={pagination.offset === 0}
                className="px-4 py-2 border rounded-lg disabled:opacity-50"
              >
                ← Previous
              </button>
              <button
                onClick={() =>
                  setPagination({
                    ...pagination,
                    offset: pagination.offset + pagination.limit
                  })
                }
                disabled={pagination.offset + pagination.limit >= total}
                className="px-4 py-2 border rounded-lg disabled:opacity-50"
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}

      {/* Finding Detail Modal */}
      {selectedFinding && detailModalOpen && (
        <FindingDetailModal
          finding={selectedFinding}
          isOpen={detailModalOpen}
          onClose={() => {
            setDetailModalOpen(false)
            setSelectedFinding(null)
          }}
        />
      )}
    </div>
  )
}

function FindingDetailModal({ finding, isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('problem')
  const [newComment, setNewComment] = useState('')
  const [newStatus, setNewStatus] = useState(finding.status)
  const queryClient = useQueryClient()

  const { data: details, refetch } = useQuery({
    queryKey: ['finding-detail', finding.id],
    queryFn: () => api.get(`/findings/${finding.id}`).then(r => r.data),
    enabled: isOpen
  })

  if (!isOpen || !details) return null

  const handleStatusChange = async () => {
    try {
      await api.patch(`/findings/${finding.id}/status`, {
        new_status: newStatus,
        reason: 'Status updated'
      })
      refetch()
      queryClient.invalidateQueries({ queryKey: ['findings'] })
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleAddComment = async () => {
    if (!newComment.trim()) return
    try {
      await api.post(`/findings/${finding.id}/comments`, {
        comment_text: newComment,
        is_internal: false
      })
      refetch()
      setNewComment('')
    } catch (error) {
      console.error('Error:', error)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-4xl max-h-96 overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-start">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {finding.rule_id}: {finding.object_name}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {finding.object_type} | {finding.severity}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl"
          >
            ×
          </button>
        </div>

        <div className="bg-gray-50 px-6 py-4 border-b flex justify-between items-center">
          <div>
            <label className="text-sm font-medium text-gray-700">Status:</label>
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
              className="mt-1 border rounded-lg px-3 py-1 text-sm"
            >
              <option value="Open">Open</option>
              <option value="Pending">Pending</option>
              <option value="In Progress">In Progress</option>
              <option value="Optimized">Optimized</option>
              <option value="CR_Submitted">CR Submitted</option>
              <option value="Acknowledged">Acknowledged</option>
            </select>
          </div>
          {newStatus !== finding.status && (
            <button
              onClick={handleStatusChange}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
            >
              Save Status
            </button>
          )}
        </div>

        <div className="flex border-b">
          {['problem', 'solution', 'help', 'comments', 'history'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 text-sm font-medium border-b-2 ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="px-6 py-4">
          {activeTab === 'problem' && (
            <div>
              <h3 className="font-semibold mb-2">Issue</h3>
              <p className="text-gray-700 mb-4">{finding.issue}</p>
              {details.schema_object && (
                <div>
                  <h3 className="font-semibold mb-2">Object Definition</h3>
                  <pre className="bg-gray-100 p-3 rounded text-xs overflow-auto max-h-48">
                    {details.schema_object.definition}
                  </pre>
                </div>
              )}
            </div>
          )}

          {activeTab === 'solution' && (
            <div>
              <h3 className="font-semibold mb-2">Recommendation</h3>
              <p className="text-gray-700">{finding.recommendation}</p>
            </div>
          )}

          {activeTab === 'help' && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-blue-900">
                Help content for {finding.rule_id} will load here
              </p>
            </div>
          )}

          {activeTab === 'comments' && (
            <div className="space-y-4">
              {details.comments && details.comments.length > 0 && (
                <div className="space-y-3">
                  {details.comments.map(comment => (
                    <div key={comment.id} className="bg-gray-50 rounded p-3">
                      <p className="text-sm font-medium text-gray-900">
                        User #{comment.user_id}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">
                        {comment.comment_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="w-full border rounded-lg px-3 py-2 text-sm"
                rows={3}
              />
              <button
                onClick={handleAddComment}
                disabled={!newComment.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50"
              >
                Post Comment
              </button>
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-3">
              {details.status_history && details.status_history.length > 0 ? (
                details.status_history.map((entry, i) => (
                  <div key={i} className="border-l-4 border-blue-500 pl-4 py-2">
                    <p className="text-sm font-medium">
                      {entry.old_status} → {entry.new_status}
                    </p>
                    <p className="text-xs text-gray-600">{entry.changed_at}</p>
                    {entry.reason && (
                      <p className="text-xs text-gray-700 mt-1">{entry.reason}</p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-gray-500">No status changes yet</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
