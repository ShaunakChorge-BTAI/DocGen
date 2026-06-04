import { useQuery } from '@tanstack/react-query'
import { runApi } from '../lib/api'

interface Props {
  selectedRun:    number | null
  setSelectedRun: (v: number | null) => void
}

export default function RunContextBar({ selectedRun, setSelectedRun }: Props) {
  const { data: runsData } = useQuery({
    queryKey: ['runs'],
    queryFn:  () => runApi.list().then(r => r.data.runs),
  })

  if (!selectedRun) return null

  const run     = runsData?.find((r: any) => r.id === selectedRun)
  const health  = run?.health_score ?? null
  const hColor  = health === null ? '#94a3b8'
                : health >= 80   ? '#10b981'
                : health >= 60   ? '#f59e0b'
                                 : '#ef4444'

  return (
    <div
      className="flex items-center gap-3 px-6 py-2 bg-surface-lowest flex-shrink-0"
      style={{ borderBottom: `2px solid ${hColor}`, minHeight: 36 }}
    >
      {/* Pulse dot */}
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: hColor }} />

      {/* Run label */}
      <span className="text-xs font-semibold text-on-surface truncate max-w-xs">
        {run?.label ?? `Run #${selectedRun}`}
      </span>

      <span className="text-on-surface-variant text-xs opacity-40">·</span>

      {/* DB name */}
      <div className="flex items-center gap-1">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 12 }}>storage</span>
        <span className="text-xs text-on-surface-variant font-mono">{run?.db_name ?? '…'}</span>
      </div>

      <span className="text-on-surface-variant text-xs opacity-40">·</span>

      {/* Date */}
      <div className="flex items-center gap-1">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 12 }}>schedule</span>
        <span className="text-xs text-on-surface-variant">
          {run?.timestamp ? new Date(run.timestamp).toLocaleString() : '…'}
        </span>
      </div>

      <span className="text-on-surface-variant text-xs opacity-40">·</span>

      {/* Health */}
      <div className="flex items-center gap-1">
        <span className="material-symbols-outlined" style={{ fontSize: 12, color: hColor }}>favorite</span>
        <span className="text-xs font-bold" style={{ color: hColor }}>
          {health !== null ? `${health}%` : '—'}
        </span>
      </div>

      <span className="text-on-surface-variant text-xs opacity-40">·</span>

      {/* Findings */}
      <div className="flex items-center gap-1">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 12 }}>bug_report</span>
        <span className="text-xs text-on-surface-variant">
          {run?.total_issues ?? 0} findings
        </span>
      </div>

      <div className="flex-1" />

      {/* Clear button */}
      <button
        onClick={() => setSelectedRun(null)}
        title="Clear run selection"
        className="flex items-center gap-1 px-2 py-0.5 rounded text-xs text-on-surface-variant hover:bg-surface-low hover:text-on-surface transition-colors"
      >
        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>close</span>
        Clear
      </button>
    </div>
  )
}
