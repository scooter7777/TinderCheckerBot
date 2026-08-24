import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'

const ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
}

export default function ToastStack({ toasts, onDismiss }) {
  return (
    <div className="toast-stack">
      {toasts.map((toast) => {
        const Icon = ICONS[toast.type] || Info
        return (
          <button
            key={toast.id}
            className={`toast ${toast.type}`}
            onClick={() => onDismiss(toast.id)}
            type="button"
          >
            <Icon size={16} />
            <span>{toast.message}</span>
            <X size={14} className="toast-x" />
          </button>
        )
      })}
    </div>
  )
}
