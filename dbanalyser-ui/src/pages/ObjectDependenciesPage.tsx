import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, dbApi } from '../lib/api'
import PageHeader from '../components/PageHeader'

interface DependentObject {
  schema_name: string
  object_name: string
  object_type: string
  definition: string | null
}

const OBJECT_TYPES = [
  { value: 'table', label: 'Table' },
  { value: 'view', label: 'View' },
  { value: 'stored procedure', label: 'Stored Procedure' },
  { value: 'function', label: 'Function' },
  { value: 'trigger', label: 'Trigger' },
]

interface Database {
  id: number
  name: string
}

export default function ObjectDependenciesPage() {
  const [selectedDb, setSelectedDb] = useState<string>('')
  const [selectedObjectType, setSelectedObjectType] = useState<string>('')
  const [selectedObject, setSelectedObject] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [dependencies, setDependencies] = useState<DependentObject[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dbRegistryId, setDbRegistryId] = useState<number | null>(null)

  // Fetch database ID when database is selected
  const { data: databases } = useQuery({
    queryKey: ['databases', false],
    queryFn: async () => {
      try {
        const response = await dbApi.list(false)
        console.log('[ObjectDeps] Databases fetched:', response.data)
        return response.data || []
      } catch (err) {
        console.error('[ObjectDeps] Failed to fetch databases:', err)
        return []
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Update dbRegistryId when selectedDb changes
  useEffect(() => {
    console.log('[ObjectDeps] selectedDb:', selectedDb, 'databases:', databases)
    if (selectedDb && databases && databases.length > 0) {
      const db = databases.find((d: any) => d.name === selectedDb)
      console.log('[ObjectDeps] Found database:', db)
      setDbRegistryId(db?.id || null)
    }
  }, [selectedDb, databases])

  // Fetch available objects from ingested schema
  const { data: objects, isLoading: objectsLoading } = useQuery({
    queryKey: ['schema-objects', dbRegistryId, selectedObjectType],
    queryFn: async () => {
      if (!dbRegistryId || !selectedObjectType) return []
      try {
        console.log('[ObjectDeps] Fetching ingested objects for:', { dbRegistryId, selectedObjectType })
        const response = await api.get<any>(`/schema/`, {
          params: { db_registry_id: dbRegistryId, object_type: selectedObjectType, limit: 1000 },
        })
        console.log('[ObjectDeps] Ingested objects fetched:', response.data)
        return response.data?.objects || []
      } catch (err) {
        console.error('[ObjectDeps] Failed to fetch ingested objects:', err)
        return []
      }
    },
    enabled: !!dbRegistryId && !!selectedObjectType,
  })

  // Filter objects based on search query
  const filteredObjects = (objects || []).filter(obj =>
    `${obj.schema_name}.${obj.object_name}`.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Fetch dependencies for selected object
  useEffect(() => {
    if (!selectedObject || !dbRegistryId || !selectedObjectType) return

    setLoading(true)
    setError(null)

    // TODO: Implement /schema/dependencies endpoint
    // For now, show a placeholder message
    setTimeout(() => {
      setDependencies([])
      setLoading(false)
    }, 500)
  }, [selectedObject, selectedObjectType, dbRegistryId])

  const dependentsByType = dependencies.reduce((acc, obj) => {
    if (!acc[obj.object_type]) {
      acc[obj.object_type] = []
    }
    acc[obj.object_type].push(obj)
    return acc
  }, {} as Record<string, DependentObject[]>)

  return (
    <div>
      <PageHeader
        title="Object Dependencies"
        subtitle="View objects that depend on your selected database object"
      />

      <div className="grid grid-cols-12 gap-6">
        {/* Selection Panel */}
        <div className="col-span-4 space-y-4">
          {/* Object Type Selector */}
          {/* Database Selector */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <label className="text-sm font-semibold text-on-surface block mb-3">Database</label>
            <select
              value={selectedDb}
              onChange={(e) => {
                setSelectedDb(e.target.value)
                setSelectedObjectType('')
                setSelectedObject('')
                setSearchQuery('')
              }}
              className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="">Select a database…</option>
              {(databases || []).map((db: any) => (
                <option key={db.name} value={db.name}>{db.name}</option>
              ))}
            </select>
          </div>

          {/* Object Type Selector */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <label className="text-sm font-semibold text-on-surface block mb-3">Object Type</label>
            {!selectedDb ? (
              <div className="text-sm text-on-surface-variant">Please select a database first</div>
            ) : (
              <select
                value={selectedObjectType}
                onChange={(e) => {
                  setSelectedObjectType(e.target.value)
                  setSelectedObject('')
                  setSearchQuery('')
                }}
                className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="">Select object type…</option>
                {OBJECT_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Object Search & Selector */}
          {selectedObjectType && (
            <div className="bg-surface-lowest rounded-xl p-5 shadow-card space-y-3">
              <label className="text-sm font-semibold text-on-surface block">Search & Select Object</label>

              {objectsLoading ? (
                <div className="text-sm text-on-surface-variant py-2">Loading objects...</div>
              ) : !dbRegistryId ? (
                <div className="text-sm text-on-surface-variant py-2">Database ID not found</div>
              ) : !objects || objects.length === 0 ? (
                <div className="text-sm text-on-surface-variant py-2">No objects of type "{selectedObjectType}" found</div>
              ) : (
                <>
                  <input
                    type="text"
                    placeholder="Search by name..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />

                  <select
                    value={selectedObject}
                    onChange={(e) => {
                      setSelectedObject(e.target.value)
                      setSearchQuery('')
                    }}
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    <option value="">Select object…</option>
                    {filteredObjects.length > 0 ? (
                      filteredObjects.map((obj: any) => (
                        <option key={`${obj.schema_name}.${obj.object_name}`} value={`${obj.schema_name}.${obj.object_name}`}>
                          {obj.schema_name}.{obj.object_name}
                        </option>
                      ))
                    ) : searchQuery ? (
                      <option disabled>No matches for "{searchQuery}"</option>
                    ) : (
                      <option disabled>No objects found</option>
                    )}
                  </select>
                </>
              )}
            </div>
          )}

          {selectedObject && (
            <div className="bg-blue-50 rounded-xl p-4 text-sm font-medium flex items-center gap-2 text-primary">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
              <div>
                <div>Selected: <span className="font-semibold">{selectedObject}</span></div>
                <div className="text-xs text-primary/80 mt-1">Type: {selectedObjectType}</div>
              </div>
            </div>
          )}
        </div>

        {/* Dependencies Grid */}
        <div className="col-span-8">
          {!selectedObject && (
            <div className="bg-surface-lowest rounded-xl p-8 text-center">
              <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 40 }}>search</span>
              <div className="mt-2 text-sm text-on-surface-variant">Select an object to view its dependencies</div>
            </div>
          )}

          {selectedObject && (
            <div className="bg-blue-50 rounded-xl p-8 text-center">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 40 }}>info</span>
              <div className="mt-2 text-sm text-primary font-medium">Dependencies feature coming soon</div>
              <div className="mt-1 text-xs text-primary/80">
                Selected: <span className="font-semibold">{selectedObject}</span>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
