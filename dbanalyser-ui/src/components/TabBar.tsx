interface Tab { id: string; label: string; icon?: string }
interface Props { tabs: Tab[]; active: string; onChange: (id: string) => void }

export default function TabBar({ tabs, active, onChange }: Props) {
  return (
    <div className="flex border-b border-surface-low mb-6" style={{ borderColor: 'rgba(74,68,85,0.1)' }}>
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            active === t.id
              ? 'border-primary text-primary'
              : 'border-transparent text-on-surface-variant hover:text-on-surface'
          }`}
        >
          {t.icon && <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{t.icon}</span>}
          {t.label}
        </button>
      ))}
    </div>
  )
}
