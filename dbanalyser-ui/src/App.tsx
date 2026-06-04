import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import AnalysisPage from './pages/AnalysisPage'
import RunAssessmentPage from './pages/RunAssessmentPage'
import SchemaQualityPage from './pages/SchemaQualityPage'
import CompliancePage from './pages/CompliancePage'
import LiveDbPage from './pages/LiveDbPage'
import ReportsPage from './pages/ReportsPage'
import AdministrationPage from './pages/AdministrationPage'
import CodeOptimiserPage    from './pages/CodeOptimiserPage'
import ObjectDependenciesPage from './pages/ObjectDependenciesPage'
import SchedulesPage        from './pages/SchedulesPage'
import UsersOrgPage         from './pages/UsersOrgPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-on-surface-variant">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="analysis" element={<AnalysisPage />} />
        <Route path="run-assessment" element={<RunAssessmentPage />} />
        <Route path="schema-quality" element={<SchemaQualityPage />} />
        <Route path="compliance" element={<CompliancePage />} />
        <Route path="live-db" element={<LiveDbPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="administration"  element={<AdministrationPage />} />
        <Route path="code-optimiser"    element={<CodeOptimiserPage />} />
        <Route path="object-dependencies" element={<ObjectDependenciesPage />} />
        <Route path="schedules"         element={<SchedulesPage />} />
        <Route path="users-org"         element={<UsersOrgPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
