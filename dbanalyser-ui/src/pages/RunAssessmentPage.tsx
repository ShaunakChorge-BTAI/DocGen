import { useState, useRef, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { dbApi } from '../lib/api'
import PageHeader from '../components/PageHeader'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function RunAssessmentPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()

  const [selectedDb, setDb]   = useState('')
  const [label, setLabel]     = useState('')
  const [running, setRunning] = useState(false)
  const [done, setDone]       = useState(false)
  const [log, setLog]         = useState<string[]>([])
  const [options, setOptions] = useState({ dmv: true, extended: true })
  const logRef  = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: dbData } = useQuery({ queryKey: ['databases', true], queryFn: () => dbApi.list(true).then(r => r.data) })
  const dbs: any[] = dbData ?? []

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  // Clean up polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const addLog = (line: string) => setLog(prev => [...prev, line])

  const startRun = async () => {
    if (!selectedDb) return
    setRunning(true)
    setDone(false)
    setLog([`[INFO] Starting assessment for ${selectedDb}…`])

    try {
      const body: Record<string, any> = {
        db_name:    selectedDb,
        run_dmv:    options.dmv,
        no_persist: false,
      }
      if (label.trim()) body.label = label.trim()

      addLog('[INFO] Submitting analysis job to API…')
      const res = await fetch(`${API_BASE}/runs/trigger`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      })
      const { job_id } = await res.json()
      addLog(`[INFO] Job accepted — id: ${job_id}`)
      addLog('[INFO] Waiting for analysis engine…')

      // Poll every 2 s
      pollRef.current = setInterval(async () => {
        try {
          const s = await fetch(`${API_BASE}/runs/jobs/${job_id}`).then(r => r.json())

          if (s.status === 'running') {
            addLog('[INFO] Analysis in progress…')
          } else if (s.status === 'done') {
            clearInterval(pollRef.current!)
            addLog('[INFO] Object scanning complete.')
            addLog('[INFO] Persisting findings to PostgreSQL…')
            addLog(`[SUCCESS] Assessment finished — run id: ${s.run_id}`)
            setDone(true)
            setRunning(false)

            // Refresh queries and auto-navigate to the new run
            qc.invalidateQueries()
            if (s.run_id) {
              navigate(`/analysis?run_id=${s.run_id}`)
            }
          } else if (s.status === 'failed') {
            clearInterval(pollRef.current!)
            addLog(`[ERROR] Analysis failed: ${s.message}`)
            setRunning(false)
          }
        } catch {
          addLog('[WARN] Polling error — retrying…')
        }
      }, 2000)
    } catch (err: any) {
      addLog(`[ERROR] Failed to start: ${err.message ?? err}`)
      setRunning(false)
    }
  }

  const stopRun = () => {
    if (pollRef.current) clearInterval(pollRef.current!)
    setRunning(false)
    addLog('[INFO] Assessment cancelled by user.')
  }

  const toggle = (k: keyof typeof options) => setOptions(p => ({ ...p, [k]: !p[k] }))

  return (
    <div>
      <PageHeader title="Run Assessment" subtitle="Trigger a new analysis run against a registered database" />

      <div className="grid grid-cols-12 gap-6">
        {/* Config panel */}
        <div className="col-span-5 space-y-4">

          {/* Target database */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-4">Target Database</div>
            <select
              value={selectedDb}
              onChange={(e) => setDb(e.target.value)}
              className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="">Select database…</option>
              {dbs.map((db: any) => <option key={db.id} value={db.name}>{db.name}</option>)}
            </select>
          </div>

          {/* Optional run label */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-3">Run Label <span className="text-xs font-normal text-on-surface-variant">(optional)</span></div>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. sprint-42-release"
              className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
              disabled={running}
            />
          </div>

          {/* Analysis modules */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-4">Analysis Modules</div>
            <div className="space-y-3">
              {([
                { key: 'dmv',      label: 'Live DMV Checks',        desc: 'Missing indexes, wait stats, top queries',       icon: 'speed'   },
                { key: 'extended', label: 'Extended Schema Checks',  desc: 'PK analysis, index duplicates, type mismatches', icon: 'schema'  },
              ] as { key: keyof typeof options; label: string; desc: string; icon: string }[]).map(({ key, label: lbl, desc, icon }) => (
                <label key={key} className="flex items-start gap-3 cursor-pointer group">
                  <div className="mt-0.5">
                    <input
                      type="checkbox"
                      checked={options[key]}
                      onChange={() => toggle(key)}
                      disabled={running}
                      className="w-4 h-4 rounded accent-primary"
                    />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 14 }}>{icon}</span>
                      <span className="text-sm font-medium text-on-surface">{lbl}</span>
                    </div>
                    <div className="text-xs text-on-surface-variant mt-0.5">{desc}</div>
                  </div>
                </label>
              ))}
              {/* Coming soon modules */}
              {[
                { label: 'Compliance Pack',      desc: 'SOX, GDPR, RBI rules — coming soon', icon: 'gavel'     },
                { label: 'AI Recommendations',   desc: 'Ollama-powered SQL optimisation', icon: 'smart_toy' },
              ].map(({ label: lbl, desc, icon }) => (
                <div key={lbl} className="flex items-start gap-3 opacity-40 cursor-not-allowed">
                  <div className="mt-0.5">
                    <input type="checkbox" disabled className="w-4 h-4 rounded" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 14 }}>{icon}</span>
                      <span className="text-sm font-medium text-on-surface">{lbl}</span>
                    </div>
                    <div className="text-xs text-on-surface-variant mt-0.5">{desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={startRun}
              disabled={running || !selectedDb}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                {running ? 'hourglass_empty' : 'play_arrow'}
              </span>
              {running ? 'Running…' : 'Start Assessment'}
            </button>
            {running && (
              <button
                onClick={stopRun}
                className="px-4 py-2.5 rounded-lg text-sm font-medium bg-surface-low text-error hover:bg-red-50 transition-colors"
              >
                Stop
              </button>
            )}
          </div>

          {done && (
            <div className="bg-green-50 rounded-xl p-4 text-sm text-success font-medium flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>check_circle</span>
              Assessment complete! Results auto-selected — navigate to Analysis to explore.
            </div>
          )}
        </div>

        {/* Log terminal */}
        <div className="col-span-7">
          <div className="bg-gray-950 rounded-xl overflow-hidden shadow-float h-full min-h-96">
            <div className="bg-gray-900 px-4 py-2.5 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="ml-2 text-xs text-gray-400 font-mono">dbanalyser — assessment log</span>
            </div>
            <div ref={logRef} className="p-4 font-mono text-xs text-green-400 leading-5 overflow-y-auto h-80 space-y-0.5">
              {log.length === 0 ? (
                <div className="text-gray-600">Select a database and click Start Assessment…</div>
              ) : (
                log.map((line, i) => {
                  const isError   = line.includes('[ERROR]')
                  const isWarn    = line.includes('[WARN]')
                  const isInfo    = line.includes('[INFO]')
                  const isSuccess = line.includes('[SUCCESS]')
                  return (
                    <div
                      key={i}
                      className={
                        isError   ? 'text-red-400'    :
                        isSuccess ? 'text-green-300'  :
                        isWarn    ? 'text-yellow-400' :
                        isInfo    ? 'text-blue-400'   : 'text-green-400'
                      }
                    >
                      {line}
                    </div>
                  )
                })
              )}
              {running && <div className="text-gray-500 animate-pulse">▋</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
