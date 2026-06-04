export function LoadingSpinner({ size = 24, label = 'Loading...' }: { size?: number; label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center">
      <div className="animate-spin">
        <span className="material-symbols-outlined text-primary" style={{ fontSize: size }}>
          hourglass_empty
        </span>
      </div>
      {label && <div className="mt-2 text-sm text-on-surface-variant">{label}</div>}
    </div>
  )
}

export function LoadingDot() {
  return (
    <div className="flex gap-1 items-center justify-center">
      <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0s' }} />
      <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.2s' }} />
      <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.4s' }} />
    </div>
  )
}
