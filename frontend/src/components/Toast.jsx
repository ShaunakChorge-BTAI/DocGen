import { useEffect } from "react";

export function useToast(toasts, setToasts) {
  function addToast(message, type = "info") {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }
  return addToast;
}

export default function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          {t.type === "success" && "✓ "}
          {t.type === "error" && "✕ "}
          {t.type === "info" && "ℹ "}
          {t.message}
        </div>
      ))}
    </div>
  );
}
