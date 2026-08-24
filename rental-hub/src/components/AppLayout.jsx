import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell,
  KeyRound,
  LayoutDashboard,
  Plus,
  ShieldAlert,
  Store,
  UserRound,
} from 'lucide-react'
import { useStore } from '../store'

function NotificationPanel({ open, onClose, isOwner }) {
  const navigate = useNavigate()
  const { notifications, tasks, markAllRead, markNotificationRead } = useStore()

  if (!open) return null

  const visibleNotifications = isOwner
    ? notifications.filter((item) => item.type !== 'order')
    : notifications.filter((item) => item.type === 'order')

  const openItem = (item) => {
    markNotificationRead(item.id)
    onClose()
    if (item.action === 'verify') {
      navigate(isOwner ? '/owner/verify' : '/rentals')
    } else if (item.action === 'order') {
      navigate(isOwner ? '/owner' : '/rentals')
    }
  }

  return (
    <div className="panel-backdrop" onClick={onClose} role="presentation">
      <aside className="notify-panel" onClick={(event) => event.stopPropagation()}>
        <div className="notify-head">
          <div>
            <div className="eyebrow">Notifications</div>
            <h2>Account activity</h2>
          </div>
          <div className="notify-actions">
            <button className="ghost-btn" onClick={markAllRead}>
              Mark all read
            </button>
            <button className="icon-btn" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
        </div>

        {isOwner && tasks.length > 0 && (
          <div className="task-alert-strip">
            <ShieldAlert size={18} />
            <span>{tasks.length} accounts need attention</span>
            <button onClick={() => { onClose(); navigate('/owner/verify') }}>Handle now</button>
          </div>
        )}

        <div className="notify-list">
          {visibleNotifications.map((item) => (
            <button
              key={item.id}
              className={`notify-item ${item.read ? 'is-read' : ''} severity-${item.severity}`}
              onClick={() => openItem(item)}
            >
              <span className="notify-dot" />
              <span className="notify-body">
                <span className="notify-title">{item.title}</span>
                <span className="notify-message">{item.message}</span>
                <span className="notify-time">{item.time}</span>
              </span>
            </button>
          ))}
        </div>
      </aside>
    </div>
  )
}

export default function AppLayout() {
  const [notifyOpen, setNotifyOpen] = useState(false)
  const location = useLocation()
  const { notifications, tasks } = useStore()

  const isOwner = location.pathname === '/owner' || location.pathname.startsWith('/owner/')
  const sideNotifications = notifications.filter((item) =>
    isOwner ? item.type !== 'order' : item.type === 'order',
  )
  const unread = sideNotifications.filter((item) => !item.read).length + (isOwner ? tasks.length : 0)
  const navClass = ({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to={isOwner ? '/owner' : '/'} className="brand">
            <span className="brand-mark">
              <KeyRound size={21} />
            </span>
            <span className="brand-text">
              <strong>RentPass</strong>
              <small>ACCOUNT RENTALS</small>
            </span>
          </NavLink>

          <nav className="main-nav" aria-label="Main navigation">
            {isOwner ? (
              <>
                <NavLink to="/owner" className={navClass}>
                  <KeyRound size={17} />
                  Owner portal
                </NavLink>
                <NavLink to="/owner/publish" className={navClass}>
                  <Plus size={17} />
                  List account
                </NavLink>
                <NavLink to="/owner/verify" className={navClass}>
                  <ShieldAlert size={17} />
                  Verify center
                  {tasks.length > 0 && <span className="nav-badge">{tasks.length}</span>}
                </NavLink>
              </>
            ) : (
              <>
                <NavLink to="/" className={navClass} end>
                  <Store size={17} />
                  Marketplace
                </NavLink>
                <NavLink to="/rentals" className={navClass}>
                  <LayoutDashboard size={17} />
                  My rentals
                </NavLink>
              </>
            )}
          </nav>

          <div className="topbar-actions">
            <button
              className="icon-btn notify-btn"
              aria-label="Notifications"
              onClick={() => setNotifyOpen((value) => !value)}
            >
              <Bell size={19} />
              {unread > 0 && <span className="bell-badge">{unread}</span>}
            </button>
            <span className="avatar">
              <UserRound size={18} />
            </span>
          </div>
        </div>
      </header>

      <NotificationPanel open={notifyOpen} onClose={() => setNotifyOpen(false)} isOwner={isOwner} />

      <main className="page-main">
        <Outlet />
      </main>

      <nav
        className={isOwner ? 'mobile-nav owner' : 'mobile-nav renter'}
        aria-label="Mobile navigation"
      >
        {isOwner ? (
          <>
            <NavLink to="/owner" className={({ isActive }) => (isActive ? 'active' : '')}>
              <KeyRound size={20} />
              Owner
            </NavLink>
            <NavLink to="/owner/publish" className="mobile-publish">
              <Plus size={22} />
            </NavLink>
            <NavLink to="/owner/verify" className={({ isActive }) => (isActive ? 'active' : '')}>
              <ShieldAlert size={20} />
              Verify
              {tasks.length > 0 && <span className="nav-badge">{tasks.length}</span>}
            </NavLink>
            <button onClick={() => setNotifyOpen(true)} aria-label="Notifications">
              <Bell size={20} />
              Alerts
              {unread > 0 && <span className="nav-badge">{unread}</span>}
            </button>
          </>
        ) : (
          <>
            <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')} end>
              <Store size={20} />
              Market
            </NavLink>
            <NavLink to="/rentals" className={({ isActive }) => (isActive ? 'active' : '')}>
              <LayoutDashboard size={20} />
              Rentals
            </NavLink>
            <button onClick={() => setNotifyOpen(true)} aria-label="Notifications">
              <Bell size={20} />
              Alerts
              {unread > 0 && <span className="nav-badge">{unread}</span>}
            </button>
          </>
        )}
      </nav>
    </div>
  )
}
