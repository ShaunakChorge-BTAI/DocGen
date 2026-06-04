interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: string
  color?: string
  trend?: 'up' | 'down' | 'neutral'
  onClick?: () => void
}

export default function KpiCard({ label, value, sub, icon, color = '#630ed4', onClick }: Props) {
  return (
    <div
      className={`bg-surface-lowest rounded-xl p-5 shadow-card flex flex-col gap-2 transition-all duration-150 ${
        onClick ? 'cursor-pointer hover:shadow-float hover:-translate-y-0.5 select-none' : ''
      }`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">{label}</span>
        <div className="flex items-center gap-1">
          {icon && (
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${color}18` }}>
              <span className="material-symbols-outlined" style={{ fontSize: 16, color }}>{icon}</span>
            </div>
          )}
          {onClick && (
            <span className="material-symbols-outlined text-on-surface-variant opacity-40" style={{ fontSize: 14 }}>
              arrow_forward
            </span>
          )}
        </div>
      </div>
      <div className="text-2xl font-bold text-on-surface tracking-tight" style={{ letterSpacing: '-0.02em' }}>{value}</div>
      {sub && <div className="text-xs text-on-surface-variant">{sub}</div>}
    </div>
  )
}
