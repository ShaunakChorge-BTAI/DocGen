import { useState } from 'react'
import { api } from '../lib/api'

interface DeleteRunModalProps {
  run: {
    id: number
    label: string
    db_name: string
    total_issues: number
  }
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export default function DeleteRunModal({ run, isOpen, onClose, onSuccess }: DeleteRunModalProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState('')

  const handleDelete = async () => {
    setIsDeleting(true)
    setError('')
    try {
      await api.delete(`/runs/${run.id}/hard-delete`)
      onSuccess()
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to delete run. Check API logs.')
      setIsDeleting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-surface rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-surface-low">
          <h2 className="text-lg font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-error" style={{ fontSize: 24 }}>delete</span>
            Delete Run
          </h2>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-4">
          <div className="bg-error/10 rounded-lg p-3 text-sm text-error">
            <strong>Warning:</strong> This action is permanent and cannot be undone.
          </div>

          <div className="space-y-3">
            <div>
              <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">Run</span>
              <div className="text-sm font-mono text-on-surface mt-1">{run.label}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">Database</span>
              <div className="text-sm text-on-surface mt-1">{run.db_name}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">Findings to Delete</span>
              <div className="text-sm text-on-surface mt-1">{run.total_issues} findings and associated data</div>
            </div>
          </div>

          {error && (
            <div className="bg-error/10 rounded-lg p-3 text-sm text-error">
              {error}
            </div>
          )}

          <p className="text-xs text-on-surface-variant">
            All findings, snapshots, and health records associated with this run will be permanently deleted.
          </p>
        </div>

        {/* Buttons */}
        <div className="px-6 py-4 border-t border-surface-low flex gap-3">
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-on-surface bg-surface-low hover:bg-surface-low/80 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-error hover:bg-error/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isDeleting ? (
              <>
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>hourglass_empty</span>
                Deleting…
              </>
            ) : (
              <>
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>delete</span>
                Delete Permanently
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
