const MAP: Record<string, { bg: string; text: string }> = {
  Critical: { bg: '#fee2e2', text: '#dc2626' },
  High:     { bg: '#fef3c7', text: '#d97706' },
  Medium:   { bg: '#e0f2fe', text: '#0284c7' },
  Low:      { bg: '#f0fdf4', text: '#16a34a' },
}

export default function SeverityBadge({ severity }: { severity: string }) {
  const s = MAP[severity] || { bg: '#f3f4f6', text: '#6b7280' }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium" style={{ background: s.bg, color: s.text }}>
      {severity}
    </span>
  )
}
