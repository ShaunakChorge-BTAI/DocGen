import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getNotifications, getUnreadCount, markRead, markAllRead } from "../services/api";

const TYPE_ICON = {
  status_change: "🔄",
  doc_approved: "✅",
  comment_added: "💬",
};

function timeAgo(isoString) {
  const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function NotificationBell() {
  const { authHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const dropdownRef = useRef(null);

  const fetchCount = useCallback(() => {
    getUnreadCount(authHeaders)
      .then((d) => setCount(d.count))
      .catch(() => {});
  }, [authHeaders]);

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchCount();
    const id = setInterval(fetchCount, 30_000);
    return () => clearInterval(id);
  }, [fetchCount]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function handleOpen() {
    if (!open) {
      try {
        const data = await getNotifications(authHeaders);
        setNotifications(data);
      } catch {
        // silently ignore
      }
    }
    setOpen((o) => !o);
  }

  async function handleMarkRead(id) {
    await markRead(id, authHeaders);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setCount((c) => Math.max(0, c - 1));
  }

  async function handleMarkAll() {
    await markAllRead(authHeaders);
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setCount(0);
  }

  return (
    <div className="notif-bell-wrapper" ref={dropdownRef}>
      <button
        className="notif-bell-btn"
        onClick={handleOpen}
        aria-label="Notifications"
        title="Notifications"
      >
        🔔
        {count > 0 && <span className="notif-badge">{count > 9 ? "9+" : count}</span>}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-header">
            <span>Notifications</span>
            {count > 0 && (
              <button className="notif-mark-all" onClick={handleMarkAll}>
                Mark all read
              </button>
            )}
          </div>

          <ul className="notif-list">
            {notifications.length === 0 && (
              <li className="notif-empty">No notifications yet</li>
            )}
            {notifications.map((n) => (
              <li
                key={n.id}
                className={`notif-item${n.read ? "" : " unread"}`}
                onClick={() => !n.read && handleMarkRead(n.id)}
              >
                <span className="notif-icon">{TYPE_ICON[n.type] || "📌"}</span>
                <div className="notif-body">
                  <p className="notif-message">{n.message}</p>
                  <span className="notif-time">{timeAgo(n.created_at)}</span>
                </div>
                {!n.read && <span className="notif-dot" />}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
