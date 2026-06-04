import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { api, schemaApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'

const TABS = [
  { id: 'optimise', label: 'Optimise SQL',  icon: 'auto_fix_high' },
  { id: 'history',  label: 'History',       icon: 'history' },
]

const MODELS = [
  { value: 'claude-3-5-haiku-20241022',  label: 'Claude 3.5 Haiku  (fast)'    },
  { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (balanced)' },
  { value: 'claude-3-opus-20240229',     label: 'Claude 3 Opus     (deep)'     },
]

const SEV_BG: Record<string, string> = {
  high:   'bg-red-50 border-red-200',
  medium: 'bg-amber-50 border-amber-200',
  low:    'bg-blue-50 border-blue-200',
}

function DiffBlock({ before, after, type, impact }: any) {
  return (
    <div className="rounded-lg border border-surface-low overflow-hidden text-xs font-mono">
      <div className="px-3 py-1.5 bg-surface-low flex items-center justify-between">
        <span className="text-on-surface font-semibold capitalize">{type}</span>
        {impact && <span className="text-on-surface-variant">{impact}</span>}
      </div>
      {before && (
        <div className="px-3 py-2 bg-red-50 text-red-800 whitespace-pre-wrap leading-5 border-t border-red-100">
          <span className="select-none text-red-400 mr-1">−</span>{before}
        </div>
      )}
      {after && (
        <div className="px-3 py-2 bg-green-50 text-green-800 whitespace-pre-wrap leading-5 border-t border-green-100">
          <span className="select-none text-green-400 mr-1">+</span>{after}
        </div>
      )}
    </div>
  )
}

export default function CodeOptimiserPage() {
  const location = useLocation()
  const [tab, setTab]           = useState('optimise')

  // Form state
  const [objectName, setObjectName] = useState('')
  const [sql,        setSql]        = useState('')
  const [apiKey,     setApiKey]     = useState('')
  const [model,      setModel]      = useState(MODELS[0].value)
  const [findings,   setFindings]   = useState('')
  const [showAdv,    setShowAdv]    = useState(false)
  const [sourceIssueId, setSourceIssueId] = useState<number | null>(null)

  // Schema search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showSearchResults, setShowSearchResults] = useState(false)

  // Optimization mode state - default to Quick (Ollama) for local setups
  const [optimizationMode, setOptimizationMode] = useState<'quick' | 'advanced'>('quick')
  const [ollamaAvailable, setOllamaAvailable] = useState<boolean | null>(null)

  // Result state
  const [loading,    setLoading]    = useState(false)
  const [result,     setResult]     = useState<any | null>(null)
  const [error,      setError]      = useState('')
  const [copied,     setCopied]     = useState(false)

  // History
  const { data: histData, refetch: refetchHist } = useQuery({
    queryKey: ['ai-optimizations'],
    queryFn:  () => api.get('/ai/optimizations?limit=30').then(r => r.data),
    enabled:  tab === 'history',
  })
  const history: any[] = histData?.optimizations ?? []

  const handleOptimise = async () => {
    if (!sql.trim()) { setError('Please paste some SQL before optimising.'); return }
    setLoading(true)
    setResult(null)
    setError('')
    try {
      const body: any = {
        object_name: objectName || 'ad_hoc_query',
        sql,
        persist: true,
        mode: optimizationMode,
      }
      if (optimizationMode === 'advanced') body.model = model
      if (apiKey.trim())  body.api_key  = apiKey.trim()
      if (findings.trim()) body.findings = findings.trim().split('\n').map(l => l.trim()).filter(Boolean)

      const res = await api.post('/ai/optimize', body)
      setResult(res.data)
      if (tab === 'history') refetchHist()
    } catch (e: any) {
      const errorMsg = e?.response?.data?.detail || e?.message || 'Optimisation failed.'
      if (errorMsg.includes('API key') || errorMsg.includes('ANTHROPIC_API_KEY')) {
        setError('API key not configured. Using Quick (Ollama) mode instead. Select "Quick (Ollama)" above and try again.')
      } else {
        setError(errorMsg)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSearchObjects = async (query: string) => {
    setSearchQuery(query)
    if (!query.trim()) {
      setSearchResults([])
      setShowSearchResults(false)
      return
    }
    setIsSearching(true)
    try {
      const res = await schemaApi.search(query)
      setSearchResults(res.data.results ?? [])
      setShowSearchResults(true)
    } catch (e) {
      console.error('Schema search failed:', e)
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }

  const selectObject = (obj: any) => {
    const fullName = obj.schema_name ? `${obj.schema_name}.${obj.object_name}` : obj.object_name
    setObjectName(fullName)
    setSql(obj.definition || '')
    setSearchQuery('')
    setShowSearchResults(false)
    setSearchResults([])
  }

  // Load SQL from navigation state if passed from Analysis page
  useEffect(() => {
    const state = location.state as any
    if (state?.sql) {
      setSql(state.sql)
      if (state.objectName) setObjectName(state.objectName)
      if (state.sourceIssueId) setSourceIssueId(state.sourceIssueId)
    }
  }, [])

  // Check Ollama availability on mount
  useEffect(() => {
    const checkOllama = async () => {
      try {
        // Try to check Ollama health from the backend
        const response = await api.get('/ai/health')
        const data = response.data
        setOllamaAvailable(data?.ollama_available ?? false)
      } catch (e) {
        // Fallback: Try direct Ollama check at configured URL
        try {
          await fetch('http://172.19.25.94:11434/api/tags', {
            method: 'GET',
            mode: 'no-cors'
          })
          setOllamaAvailable(true)
        } catch {
          setOllamaAvailable(false)
        }
      }
    }
    checkOllama()
  }, [])

  const confidenceColor = (score: number) =>
    score >= 0.8 ? '#10b981' : score >= 0.5 ? '#f59e0b' : '#ef4444'

  return (
    <div>
      <PageHeader
        title="SQL Code Optimiser"
        subtitle="AI-powered SQL optimisation using Claude — paste code, get instant improvements"
      />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* ── Optimise tab ──────────────────────────────────────────────────── */}
      {tab === 'optimise' && (
        <div className="grid grid-cols-12 gap-6">

          {/* ── Left: Input panel ────────────────────────────────────────── */}
          <div className="col-span-5 space-y-4">

            {/* Object name */}
            <div className="bg-surface-lowest rounded-xl p-4 shadow-card space-y-3">
              <div className="text-sm font-semibold text-on-surface">SQL Input</div>

              <div className="relative">
                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
                  Object / Query Name
                </label>
                <div className="relative">
                  <input
                    value={searchQuery || objectName}
                    onChange={e => handleSearchObjects(e.target.value)}
                    onFocus={() => searchQuery && setShowSearchResults(true)}
                    placeholder="Search database objects… (e.g. usp_GetCustomerOrders)"
                    className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                  {isSearching && (
                    <div className="absolute right-3 top-2.5">
                      <div className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
                    </div>
                  )}
                </div>

                {/* Search results dropdown */}
                {showSearchResults && searchResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-surface-lowest rounded-lg shadow-lg border border-surface-low z-10 max-h-48 overflow-y-auto">
                    {searchResults.map((obj, i) => (
                      <button
                        key={i}
                        onClick={() => selectObject(obj)}
                        className="w-full text-left px-3 py-2.5 hover:bg-surface-low transition-colors border-b border-surface-low last:border-0 text-sm"
                      >
                        <div className="font-mono text-xs text-on-surface-variant">{obj.schema_name}.{obj.object_name}</div>
                        <div className="text-xs text-on-surface-variant">{obj.object_type}</div>
                      </button>
                    ))}
                  </div>
                )}

                {/* No results message */}
                {showSearchResults && !isSearching && searchQuery && searchResults.length === 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-surface-lowest rounded-lg shadow-lg border border-surface-low z-10 px-3 py-2.5 text-xs text-on-surface-variant">
                    No objects found. Try a different search term.
                  </div>
                )}

                {/* Current object info */}
                {objectName && !searchQuery && (
                  <div className="mt-2 text-xs text-on-surface-variant">
                    Selected: <span className="font-mono text-on-surface">{objectName}</span>
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
                  SQL Code <span className="text-error">*</span>
                </label>
                <textarea
                  value={sql}
                  onChange={e => setSql(e.target.value)}
                  rows={18}
                  placeholder={"-- Paste your T-SQL here\nSELECT c.CustomerID, c.Name,\n       COUNT(o.OrderID) AS OrderCount\nFROM Customers c\nJOIN Orders o ON o.CustomerID = c.CustomerID\nWHERE c.IsActive = 1\nGROUP BY c.CustomerID, c.Name"}
                  className="w-full bg-gray-950 text-green-400 rounded-lg px-3 py-2.5 text-xs font-mono border-0 outline-none focus:ring-2 focus:ring-primary/30 leading-5 resize-vertical"
                  spellCheck={false}
                />
              </div>
            </div>

            {/* Optimization Mode + advanced */}
            <div className="bg-surface-lowest rounded-xl p-4 shadow-card space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-on-surface">Optimization Mode</div>
                <button
                  onClick={() => setShowAdv(!showAdv)}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                    {showAdv ? 'expand_less' : 'expand_more'}
                  </span>
                  {showAdv ? 'Hide' : 'Advanced'}
                </button>
              </div>

              {/* Mode selector */}
              <div className="grid grid-cols-1 gap-2">
                <label className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer border transition-all ${
                  optimizationMode === 'quick'
                    ? 'border-primary bg-primary/5'
                    : 'border-surface-low hover:border-primary/30'
                }`}>
                  <input
                    type="radio"
                    name="mode"
                    value="quick"
                    checked={optimizationMode === 'quick'}
                    onChange={() => setOptimizationMode('quick')}
                    className="accent-primary"
                  />
                  <div>
                    <span className="text-xs font-medium text-on-surface">Quick (Ollama)</span>
                    {ollamaAvailable === false && (
                      <div className="text-xs text-error mt-0.5">⚠ Ollama not available</div>
                    )}
                    {ollamaAvailable === true && (
                      <div className="text-xs text-success mt-0.5">✓ Ollama ready</div>
                    )}
                  </div>
                </label>

                <label className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer border transition-all ${
                  optimizationMode === 'advanced'
                    ? 'border-primary bg-primary/5'
                    : 'border-surface-low hover:border-primary/30'
                }`}>
                  <input
                    type="radio"
                    name="mode"
                    value="advanced"
                    checked={optimizationMode === 'advanced'}
                    onChange={() => setOptimizationMode('advanced')}
                    className="accent-primary"
                  />
                  <span className="text-xs font-medium text-on-surface">Advanced (Claude)</span>
                </label>
              </div>

              {/* Claude model selector - only show in advanced mode */}
              {optimizationMode === 'advanced' && (
                <div className="space-y-2 pt-2 border-t border-surface-low">
                  <div className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">Claude Model</div>
                  <div className="grid grid-cols-1 gap-2">
                    {MODELS.map(m => (
                      <label key={m.value}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer border transition-all ${
                          model === m.value
                            ? 'border-primary bg-primary/5 text-primary'
                            : 'border-surface-low hover:border-primary/30 text-on-surface-variant'
                        }`}>
                        <input
                          type="radio"
                          name="model"
                          value={m.value}
                          checked={model === m.value}
                          onChange={() => setModel(m.value)}
                          className="accent-primary"
                        />
                        <span className="text-xs font-medium">{m.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {showAdv && (
                <div className="space-y-3 pt-1">
                  <div>
                    <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
                      Anthropic API Key <span className="text-on-surface-variant opacity-50">(overrides server config)</span>
                    </label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={e => setApiKey(e.target.value)}
                      placeholder="sk-ant-…  (leave blank to use server key)"
                      className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
                      Known Findings <span className="text-on-surface-variant opacity-50">(one per line — guides the AI)</span>
                    </label>
                    <textarea
                      value={findings}
                      onChange={e => setFindings(e.target.value)}
                      rows={3}
                      placeholder={"Missing index on Orders.CustomerID\nImplicit conversion on c.IsActive"}
                      className="w-full bg-surface-low rounded-lg px-3 py-2 text-xs text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20 font-mono leading-5 resize-none"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Submit */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-error">
                {error}
              </div>
            )}
            <button
              onClick={handleOptimise}
              disabled={loading || !sql.trim()}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-all"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
            >
              <span className={`material-symbols-outlined ${loading ? 'animate-spin' : ''}`}
                    style={{ fontSize: 18 }}>
                {loading ? 'hourglass_empty' : 'auto_fix_high'}
              </span>
              {loading ? 'Analysing with Claude…' : 'Optimise SQL'}
            </button>
          </div>

          {/* ── Right: Result panel ───────────────────────────────────────── */}
          <div className="col-span-7 space-y-4">

            {/* Placeholder / Loading */}
            {!result && !loading && (
              <div className="bg-surface-lowest rounded-xl p-10 shadow-card flex flex-col items-center gap-3 text-center min-h-96 justify-center">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
                     style={{ background: 'linear-gradient(135deg, #630ed460, #7c3aed40)' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#630ed4' }}>
                    auto_fix_high
                  </span>
                </div>
                <div className="text-sm font-semibold text-on-surface">Paste SQL → Get Optimisations</div>
                <div className="text-xs text-on-surface-variant max-w-xs leading-5">
                  Claude will analyse your SQL, identify performance issues, and suggest
                  improvements with explanations and a diff view.
                </div>
                <div className="flex flex-wrap gap-2 justify-center mt-2">
                  {['Index hints', 'Query rewrites', 'Implicit conversions', 'Missing SARGability', 'Join optimisation'].map(t => (
                    <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {loading && (
              <div className="bg-surface-lowest rounded-xl p-10 shadow-card flex flex-col items-center gap-4 min-h-96 justify-center">
                <div className="w-12 h-12 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
                <div className="text-sm text-on-surface-variant">Claude is analysing your SQL…</div>
              </div>
            )}

            {result && !loading && (
              <>
                {/* No-change banner */}
                {result.no_change_needed && (
                  <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-4 flex items-start gap-3">
                    <span className="material-symbols-outlined text-success mt-0.5" style={{ fontSize: 20 }}>
                      check_circle
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-green-800">No Changes Needed</div>
                      <div className="text-xs text-green-700 mt-0.5">{result.no_change_reason || 'SQL is already optimal.'}</div>
                    </div>
                  </div>
                )}

                {/* Error from AI */}
                {result.error && (
                  <div className={`rounded-xl px-5 py-4 border text-sm ${SEV_BG['high'] || 'bg-red-50 border-red-200'}`}>
                    <div className="font-semibold text-red-800 mb-1">Optimisation Error</div>
                    <div className="text-xs text-red-700">{result.error}</div>
                  </div>
                )}

                {/* Meta row */}
                {!result.error && (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-surface-lowest rounded-xl p-3 shadow-card text-center">
                      <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Confidence</div>
                      <div className="text-lg font-bold"
                           style={{ color: confidenceColor(result.confidence_score ?? 0) }}>
                        {Math.round((result.confidence_score ?? 0) * 100)}%
                      </div>
                    </div>
                    <div className="bg-surface-lowest rounded-xl p-3 shadow-card text-center">
                      <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Changes</div>
                      <div className="text-lg font-bold text-on-surface">{result.changes?.length ?? 0}</div>
                    </div>
                    <div className="bg-surface-lowest rounded-xl p-3 shadow-card text-center">
                      <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Tokens</div>
                      <div className="text-lg font-bold text-on-surface">{result.tokens_used ?? '—'}</div>
                    </div>
                  </div>
                )}

                {/* Reasoning */}
                {result.reasoning && (
                  <div className="bg-surface-lowest rounded-xl p-4 shadow-card">
                    <div className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2">
                      Claude's Analysis
                    </div>
                    <div className="text-sm text-on-surface leading-6 whitespace-pre-wrap">{result.reasoning}</div>
                  </div>
                )}

                {/* Changes diff */}
                {result.changes?.length > 0 && (
                  <div className="bg-surface-lowest rounded-xl p-4 shadow-card space-y-3">
                    <div className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">
                      Change Breakdown ({result.changes.length})
                    </div>
                    {result.changes.map((c: any, i: number) => (
                      <DiffBlock key={i} {...c} />
                    ))}
                  </div>
                )}

                {/* Optimised SQL */}
                {result.optimized_sql && (
                  <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 bg-surface-low">
                      <span className="text-xs font-semibold text-on-surface uppercase tracking-wide">
                        Optimised SQL
                      </span>
                      <button
                        onClick={() => handleCopy(result.optimized_sql)}
                        className="flex items-center gap-1.5 text-xs text-primary hover:underline"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                          {copied ? 'check' : 'content_copy'}
                        </span>
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                    <pre className="p-4 bg-gray-950 text-green-400 text-xs font-mono leading-5 overflow-x-auto whitespace-pre-wrap">
                      {result.optimized_sql}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── History tab ───────────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div className="space-y-4">
          {history.length === 0 ? (
            <div className="bg-surface-lowest rounded-xl p-12 shadow-card flex flex-col items-center gap-3 text-center">
              <span className="material-symbols-outlined text-on-surface-variant opacity-30" style={{ fontSize: 48 }}>
                history
              </span>
              <div className="text-sm text-on-surface-variant">No optimisations yet.</div>
              <div className="text-xs text-on-surface-variant opacity-60">
                Switch to the Optimise SQL tab and run your first query.
              </div>
            </div>
          ) : (
            <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-low">
                    {['Object', 'Model', 'Confidence', 'Tokens', 'Changes', 'Date', ''].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.map((h: any, i: number) => (
                    <tr key={h.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                      <td className="px-4 py-3 font-mono text-xs text-on-surface">{h.object_name}</td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant truncate max-w-[120px]">
                        {h.model_used?.split('-').slice(0, 3).join('-') ?? '—'}
                      </td>
                      <td className="px-4 py-3 font-semibold text-sm"
                          style={{ color: confidenceColor(h.confidence_score ?? 0) }}>
                        {Math.round((h.confidence_score ?? 0) * 100)}%
                      </td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant">{h.tokens_used ?? '—'}</td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant">
                        {h.optimized_sql ? '✓' : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant">
                        {h.created_at ? new Date(h.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => {
                            setObjectName(h.object_name ?? '')
                            setSql(h.original_sql ?? '')
                            setTab('optimise')
                          }}
                          className="text-xs text-primary hover:underline"
                        >
                          Re-run
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
