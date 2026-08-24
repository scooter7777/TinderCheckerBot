import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Bell,
  CheckCheck,
  FlaskConical,
  KeyRound,
  Package,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { useStore } from '../store'

const ICONS = {
  verify: <KeyRound size={18} />,
  ban_risk: <ShieldAlert size={18} />,
  order: <Package size={18} />,
  system: <ShieldCheck size={18} />,
}

export default function NotificationPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { notifications, tasks, markAllRead, markNotificationRead, simulateEvent } = useStore()
  const [filter, setFilter] = useState('all')
  const isOwner = location.pathname.startsWith('/owner')
  const sideNotifications = notifications.filter((item) =>
    isOwner ? item.type !== 'order' : item.type === 'order',
  )

  const list = useMemo(
    () => (filter === 'unread' ? sideNotifications.filter((item) => !item.read) : sideNotifications),
    [filter, sideNotifications],
  )

  const unread = sideNotifications.filter((item) => !item.read).length

  const openItem = (item) => {
    markNotificationRead(item.id)
    if (item.action === 'verify' && isOwner) navigate('/owner/verify')
    if (item.action === 'order') navigate(isOwner ? '/owner' : '/rentals')
  }

  return (
    <div className="notifications-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Notifications</div>
          <h1>Notifications</h1>
        </div>
        <div className="notify-actions">
          <button className="ghost-btn" onClick={markAllRead}>
            <CheckCheck size={16} />
            Mark all read
          </button>
          {isOwner && (
            <button className="ghost-btn" onClick={simulateEvent}>
              <FlaskConical size={16} />
              Simulate security event
            </button>
          )}
        </div>
      </div>

      <div className="notification-summary">
        <div>
          <Bell size={19} />
          <span>Unread notifications</span>
          <strong>{unread}</strong>
        </div>
        <div>
          <ShieldAlert size={19} />
          <span>{isOwner ? 'Open alerts' : 'Order alerts'}</span>
          <strong>{isOwner ? tasks.length : 0}</strong>
        </div>
        <div>
          <Zap size={19} />
          <span>{isOwner ? 'Events today' : 'Order notifications'}</span>
          <strong>{isOwner ? tasks.length + 2 : sideNotifications.length}</strong>
        </div>
      </div>

      <div className="filter-tabs">
        <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>
          All
        </button>
        <button className={filter === 'unread' ? 'active' : ''} onClick={() => setFilter('unread')}>
          Unread
        </button>
      </div>

      <section className="notification-list">
        {list.map((item) => (
          <button
            className={`notify-item ${item.read ? 'is-read' : ''} severity-${item.severity}`}
            key={item.id}
            onClick={() => openItem(item)}
          >
            <span className={`notify-type ${item.type}`}>{ICONS[item.type]}</span>
            <span className="notify-body">
              <span className="notify-title">{item.title}</span>
              <span className="notify-message">{item.message}</span>
              <span className="notify-time">{item.time}</span>
            </span>
            {item.action !== 'none' && (
              <span className="notify-action">
                Handle
                <ArrowRight size={14} />
              </span>
            )}
          </button>
        ))}
        {!list.length && (
          <div className="empty-state">
            <Bell size={28} />
            <h3>No unread notifications</h3>
          </div>
        )}
      </section>
    </div>
  )
}
