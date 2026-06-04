import { NavLink } from 'react-router-dom'

// Groups keep the sidebar scannable. Dividers render between groups.
const NAV_GROUPS = [
  {
    label: 'Analysis',
    items: [
      { icon: 'space_dashboard', label: 'Dashboard',      to: '/dashboard'      },
      { icon: 'play_circle',     label: 'Run Assessment', to: '/run-assessment' },
      { icon: 'manage_search',   label: 'Analysis',       to: '/analysis'       },
      { icon: 'schema',          label: 'Schema Quality', to: '/schema-quality' },
      { icon: 'gavel',           label: 'Compliance',     to: '/compliance'     },
      { icon: 'storage',         label: 'Live DB',        to: '/live-db'        },
    ],
  },
  {
    label: 'Tools',
    items: [
      { icon: 'auto_fix_high',  label: 'SQL Optimiser',      to: '/code-optimiser'      },
      { icon: 'device_hub',     label: 'Object Dependencies', to: '/object-dependencies' },
      { icon: 'summarize',      label: 'Reports',            to: '/reports'             },
    ],
  },
  {
    label: 'Admin',
    items: [
      { icon: 'schedule',              label: 'Schedules',      to: '/schedules'     },
      { icon: 'people',                label: 'Users & Org',    to: '/users-org'     },
      { icon: 'admin_panel_settings',  label: 'Administration', to: '/administration'},
    ],
  },
]

export default function Sidebar() {
  return (
    <aside
      className="w-60 flex-shrink-0 bg-surface-lowest flex flex-col h-full"
      style={{ borderRight: '1px solid rgba(74,68,85,0.08)' }}
    >
      {/* Brand */}
      <div className="px-5 py-5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
            <span className="material-symbols-outlined text-white" style={{ fontSize: 16 }}>database</span>
          </div>
          <div>
            <div className="text-sm font-semibold text-on-surface tracking-tight">DBAnalyser</div>
            <div className="text-xs text-on-surface-variant">v2.0</div>
          </div>
        </div>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 px-3 overflow-y-auto space-y-0.5 pb-4">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label}>
            {/* Group divider + label (not for first group) */}
            {gi > 0 && (
              <div className="mt-3 mb-1 px-2 flex items-center gap-2">
                <div className="flex-1 h-px bg-on-surface-variant opacity-10" />
                <span className="text-[10px] font-semibold text-on-surface-variant opacity-40 uppercase tracking-widest">
                  {group.label}
                </span>
                <div className="flex-1 h-px bg-on-surface-variant opacity-10" />
              </div>
            )}

            {group.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group ${
                    isActive
                      ? 'active text-white'
                      : 'text-on-surface-variant hover:bg-surface-low hover:text-on-surface'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`material-symbols-outlined ${
                        isActive ? 'text-white' : 'text-on-surface-variant group-hover:text-primary'
                      }`}
                      style={{ fontSize: 18 }}
                    >
                      {item.icon}
                    </span>
                    {item.label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4" style={{ borderTop: '1px solid rgba(74,68,85,0.06)' }}>
        <div className="text-xs text-on-surface-variant opacity-50">LTFS · SQL Server</div>
      </div>
    </aside>
  )
}
