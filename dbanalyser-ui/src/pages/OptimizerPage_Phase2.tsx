import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { dracula } from 'react-syntax-highlighter/dist/esm/styles/prism'
import PageHeader from '../components/PageHeader'

export default function OptimizerPage_Phase2() {
  const [selectedFinding, setSelectedFinding] = useState<any>(null)
  const [activeTab, setActiveTab] = useState('suggest')
  const [sqlInput, setSqlInput] = useState('')
  const [objectType, setObjectType] = useState('Procedure')
  const [ruleId, setRuleId] = useState('')
  const [issueDesc, setIssueDesc] = useState('')

  // Get optimizer health
  const { data: health } = useQuery({
    queryKey: ['optimizer-health'],
    queryFn: () => fetch('/api/optimizer/health').then(r => r.json())
  })

  const isOllamaReady = health?.ollama_available

  if (!isOllamaReady) {
    return (
      <div className="p-6">
        <PageHeader title="SQL Optimizer" subtitle="Powered by local Ollama" />
        <div className="bg-red-50 rounded-lg p-6 text-red-700 border border-red-200">
          <h3 className="font-bold mb-2">⚠️ Ollama Not Available</h3>
          <p className="mb-4">The SQL optimizer requires Ollama to be running locally.</p>
          <div className="bg-gray-900 text-gray-100 p-4 rounded font-mono text-sm">
            <p>1. Download Ollama: https://ollama.ai</p>
            <p>2. Pull a model: <code>ollama pull mistral</code></p>
            <p>3. Start Ollama: <code>ollama serve</code></p>
            <p>4. Reload this page</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <PageHeader
        title="SQL Optimizer"
        subtitle={`Powered by local Ollama • Model: ${health?.models?.[0] || 'mistral'}`}
      />

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Input/History */}
        <div className="col-span-1 space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-bold mb-3">Optimize SQL</h3>

            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700">Rule ID</label>
                <input
                  value={ruleId}
                  onChange={(e) => setRuleId(e.target.value)}
                  placeholder="e.g., PERF001"
                  className="w-full border rounded px-3 py-2 text-sm mt-1"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700">Object Type</label>
                <select
                  value={objectType}
                  onChange={(e) => setObjectType(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm mt-1"
                >
                  <option>Procedure</option>
                  <option>Function</option>
                  <option>View</option>
                  <option>Trigger</option>
                  <option>Query</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700">Issue Description</label>
                <textarea
                  value={issueDesc}
                  onChange={(e) => setIssueDesc(e.target.value)}
                  placeholder="What's wrong?"
                  className="w-full border rounded px-3 py-2 text-sm mt-1"
                  rows={2}
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700">SQL Code</label>
                <textarea
                  value={sqlInput}
                  onChange={(e) => setSqlInput(e.target.value)}
                  placeholder="Paste SQL here..."
                  className="w-full border rounded px-3 py-2 text-sm mt-1 font-mono text-xs"
                  rows={6}
                />
              </div>

              <button
                onClick={() => {
                  if (sqlInput && ruleId) {
                    // Trigger suggestion
                  }
                }}
                className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 font-medium"
              >
                Get Suggestion
              </button>
            </div>
          </div>

          {/* Optimization History */}
          {selectedFinding && (
            <OptimizationHistory findingId={selectedFinding.id} />
          )}
        </div>

        {/* Right: Tabs */}
        <div className="col-span-2">
          <div className="bg-white rounded-lg shadow">
            {/* Tab Navigation */}
            <div className="flex border-b">
              {['suggest', 'test', 'history', 'cr'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-3 font-medium border-b-2 text-sm ${
                    activeTab === tab
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-600'
                  }`}
                >
                  {tab === 'suggest' && '💡 Suggest'}
                  {tab === 'test' && '✅ Test'}
                  {tab === 'history' && '📋 History'}
                  {tab === 'cr' && '📝 Change Request'}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="p-6">
              {activeTab === 'suggest' && <SuggestTab sqlInput={sqlInput} />}
              {activeTab === 'test' && <TestTab />}
              {activeTab === 'history' && <HistoryTab />}
              {activeTab === 'cr' && <ChangeRequestTab />}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function SuggestTab({ sqlInput }: { sqlInput: string }) {
  const [suggestion, setSuggestion] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleGetSuggestion = async () => {
    setIsLoading(true)
    try {
      // API call would go here
      // For demo purposes:
      setSuggestion({
        optimization_id: 1,
        suggested_sql: 'SELECT id, name FROM users WHERE status = 1 ORDER BY created_at DESC',
        confidence_score: 0.85,
        estimated_improvement_pct: 35,
        estimated_risk_level: 'low',
        explanation: 'Removed SELECT * and added explicit columns. Added index on status column.',
        response_time_ms: 8500,
        model: 'mistral'
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!suggestion) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p className="mb-4">Enter SQL above and click "Get Suggestion"</p>
        <button
          onClick={handleGetSuggestion}
          disabled={!sqlInput || isLoading}
          className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? 'Generating...' : 'Get Suggestion'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Badges */}
      <div className="flex gap-3">
        <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm font-medium">
          ✓ {(suggestion.confidence_score * 100).toFixed(0)}% Confidence
        </span>
        <span className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm font-medium">
          ⚡ ~{suggestion.estimated_improvement_pct}% Faster
        </span>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          suggestion.estimated_risk_level === 'low'
            ? 'bg-green-100 text-green-700'
            : 'bg-yellow-100 text-yellow-700'
        }`}>
          Risk: {suggestion.estimated_risk_level}
        </span>
      </div>

      {/* Explanation */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold mb-2">Explanation</h4>
        <p className="text-gray-700 text-sm">{suggestion.explanation}</p>
      </div>

      {/* Suggested SQL */}
      <div>
        <h4 className="font-semibold mb-2">Suggested Optimization</h4>
        <div className="bg-gray-900 rounded overflow-hidden">
          <SyntaxHighlighter language="sql" style={dracula} customStyle={{ margin: 0 }}>
            {suggestion.suggested_sql}
          </SyntaxHighlighter>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button className="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
          Test on UAT
        </button>
        <button className="flex-1 bg-gray-600 text-white py-2 rounded hover:bg-gray-700">
          Download
        </button>
      </div>

      <p className="text-xs text-gray-500">
        Processed in {suggestion.response_time_ms}ms using {suggestion.model}
      </p>
    </div>
  )
}

function TestTab() {
  const [results, setResults] = useState<any>(null)

  return (
    <div className="space-y-4">
      {!results ? (
        <div className="text-center py-8 text-gray-500">
          <p>Click "Test on UAT" from the Suggest tab to run tests</p>
        </div>
      ) : (
        <>
          {/* Performance Comparison */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Original Time</p>
              <p className="text-2xl font-bold">{results.original_time_ms}ms</p>
            </div>
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Optimized Time</p>
              <p className="text-2xl font-bold text-green-600">{results.optimized_time_ms}ms</p>
            </div>
            <div className="bg-green-50 p-4 rounded">
              <p className="text-sm text-gray-600">Improvement</p>
              <p className="text-2xl font-bold text-green-600">+{results.improvement_pct}%</p>
            </div>
          </div>

          {/* Metrics Table */}
          <div>
            <h4 className="font-semibold mb-2">Performance Metrics</h4>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">Metric</th>
                  <th className="px-4 py-2 text-right">Original</th>
                  <th className="px-4 py-2 text-right">Optimized</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {results.metrics.map((m: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2">{m.metric}</td>
                    <td className="px-4 py-2 text-right">{m.original}</td>
                    <td className="px-4 py-2 text-right text-green-600 font-medium">{m.optimized}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Data Integrity Check */}
          <div className={`p-4 rounded ${results.data_integrity_ok ? 'bg-green-50' : 'bg-red-50'}`}>
            <p className="font-medium">
              {results.data_integrity_ok ? '✓ Data Integrity OK' : '✗ Data Mismatch'}
            </p>
            <p className="text-sm text-gray-600">
              {results.original_rows === results.optimized_rows
                ? 'Original and optimized queries return same number of rows'
                : 'Row count mismatch - optimization changes results'}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2">
            <button className="flex-1 bg-green-600 text-white py-2 rounded hover:bg-green-700">
              Approve & Submit CR
            </button>
            <button className="flex-1 bg-gray-600 text-white py-2 rounded hover:bg-gray-700">
              Retry Optimization
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function HistoryTab() {
  const [history, setHistory] = useState<any[]>([])

  return (
    <div className="space-y-2">
      {history.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No optimization history yet</p>
        </div>
      ) : (
        history.map((item, i) => (
          <div key={i} className="border rounded p-4 hover:bg-gray-50">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium">Attempt #{item.attempt_number}</p>
                <p className="text-sm text-gray-600">{item.test_date}</p>
              </div>
              <span className={`px-3 py-1 rounded text-xs font-medium ${
                item.status === 'success'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-red-100 text-red-700'
              }`}>
                {item.status}
              </span>
            </div>
            {item.improvement_pct > 0 && (
              <p className="text-sm mt-2 text-green-600 font-medium">
                +{item.improvement_pct}% improvement
              </p>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function ChangeRequestTab() {
  const [crTitle, setCrTitle] = useState('')
  const [crDesc, setCrDesc] = useState('')
  const [notes, setNotes] = useState('')

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">CR Title</label>
        <input
          value={crTitle}
          onChange={(e) => setCrTitle(e.target.value)}
          placeholder="e.g., Optimize users table query"
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">Description</label>
        <textarea
          value={crDesc}
          onChange={(e) => setCrDesc(e.target.value)}
          placeholder="What's being changed and why?"
          className="w-full border rounded px-3 py-2 text-sm"
          rows={3}
        />
      </div>

      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">Implementation Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="How to apply this change..."
          className="w-full border rounded px-3 py-2 text-sm"
          rows={3}
        />
      </div>

      <button className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 font-medium">
        Submit Change Request
      </button>

      <p className="text-xs text-gray-500">
        CR will be sent to your change management system for approval
      </p>
    </div>
  )
}

function OptimizationHistory({ findingId }: { findingId: number }) {
  const { data } = useQuery({
    queryKey: ['optimization-history', findingId],
    queryFn: () => fetch(`/api/optimizer/history/${findingId}`).then(r => r.json())
  })

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-bold mb-3">Optimization History</h3>
      {!data?.history?.length ? (
        <p className="text-sm text-gray-500">No optimizations yet</p>
      ) : (
        <div className="space-y-2">
          {data.history.map((opt: any, i: number) => (
            <div key={i} className="text-sm border-l-2 border-blue-500 pl-3 py-2">
              <p className="font-medium">{opt.status}</p>
              <p className="text-xs text-gray-500">{opt.created_at}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
