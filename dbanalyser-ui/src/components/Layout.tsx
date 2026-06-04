import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import RunContextBar from './RunContextBar'
import { useState } from 'react'

export default function Layout() {
  const [db,  setDb]  = useState<string | null>(null)   // db name, e.g. "DEV_LTFS"
  const [run, setRun] = useState<number | null>(null)   // run id (integer)

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar selectedDb={db} setSelectedDb={setDb} selectedRun={run} setSelectedRun={setRun} />
        <RunContextBar selectedRun={run} setSelectedRun={setRun} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet context={{ selectedDb: db, selectedRun: run, setSelectedDb: setDb, setSelectedRun: setRun }} />
        </main>
      </div>
    </div>
  )
}
