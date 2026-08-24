import { Link, useNavigate } from 'react-router-dom'
import {
  BadgeCheck,
  CheckCircle2,
  CircleDollarSign,
  Plus,
  ShieldAlert,
  ShieldCheck,
  Star,
  TrendingUp,
} from 'lucide-react'
import { formatPrice, PLATFORM_META } from '../data'
import { useStore } from '../store'

function StatTile({ icon, label, value, tone }) {
  return (
    <div className={`stat-tile ${tone || ''}`}>
      <span className="stat-icon">{icon}</span>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  )
}

export default function OwnerPortalPage() {
  const navigate = useNavigate()
  const { accounts, orders, tasks, notifications } = useStore()

  const myAccounts = accounts.filter((item) => item.owner === 'My account')
  const onlineCount = accounts.filter((item) => item.status === 'online').length
  const revenue = orders
    .filter((item) => item.status !== 'canceled')
    .reduce((sum, item) => sum + item.amount, 0)
  const accountById = (id) => accounts.find((item) => item.id === id)

  return (
    <div className="dashboard-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Owner portal</div>
          <h1>Owner dashboard</h1>
        </div>
        <div className="page-head-actions">
          <Link to="/owner/verify" className="ghost-btn">
            <ShieldCheck size={16} />
            Verify center
          </Link>
          <Link to="/owner/publish" className="primary-btn compact">
            <Plus size={16} />
            List account
          </Link>
        </div>
      </div>

      <div className="stats-grid">
        <StatTile
          icon={<CheckCircle2 size={19} />}
          label="Listed accounts"
          value={accounts.length}
          tone="cyan"
        />
        <StatTile
          icon={<ShieldCheck size={19} />}
          label="Available now"
          value={onlineCount}
          tone="lime"
        />
        <StatTile
          icon={<CircleDollarSign size={19} />}
          label="Total earnings"
          value={`$${revenue}`}
          tone="orange"
        />
        <StatTile
          icon={<ShieldAlert size={19} />}
          label="Open alerts"
          value={tasks.length}
          tone="red"
        />
      </div>

      <section className="dashboard-section">
        <div className="section-head">
          <div>
            <div className="eyebrow">Listings</div>
            <h2>My accounts</h2>
          </div>
          <Link to="/owner/publish" className="primary-btn compact">
            <Plus size={16} />
            List account
          </Link>
        </div>
        <div className="listing-table">
          <div className="listing-head">
            <span>Account</span>
            <span>Status</span>
            <span>Price</span>
            <span>Stock</span>
            <span>Rentals</span>
          </div>
          {myAccounts.map((account) => (
            <div className="listing-row" key={account.id}>
              <div className="listing-account">
                <img src={account.image} alt="" />
                <div>
                  <strong>{account.title}</strong>
                  <span>{PLATFORM_META[account.platform].name} · {account.owner}</span>
                </div>
              </div>
              <span className={`stock-pill ${account.status}`}>
                {account.status === 'risk' ? 'Verify now' : 'Available'}
              </span>
              <strong>{formatPrice(account.priceHour)}/hr</strong>
              <span>{account.stock}</span>
              <span>{account.rentCount}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="dashboard-columns">
        <section className="dashboard-section">
          <div className="section-head">
            <div>
              <div className="eyebrow">Security</div>
              <h2>Verification & risk</h2>
            </div>
            <Link to="/owner/verify" className="ghost-btn">
              Handle all
            </Link>
          </div>
          {tasks.length ? (
            <div className="task-list">
              {tasks.map((task) => {
                const account = accountById(task.accountId)
                return (
                  <div className="task-row" key={task.id}>
                    <span className={`task-kind ${task.kind}`}>
                      {task.kind === 'verify' ? <ShieldAlert size={17} /> : <ShieldCheck size={17} />}
                    </span>
                    <div>
                      <strong>{task.title}</strong>
                      <span>{account?.title} · {task.reason}</span>
                    </div>
                    <button className="ghost-btn" onClick={() => navigate('/owner/verify')}>
                      Handle
                    </button>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="empty-state compact">
              <ShieldCheck size={22} />
              <p>No open alerts right now</p>
            </div>
          )}
        </section>

        <section className="dashboard-section">
          <div className="section-head">
            <div>
              <div className="eyebrow">Activity</div>
              <h2>Recent activity</h2>
            </div>
          </div>
          <div className="notify-list compact">
            {notifications.slice(0, 4).map((item) => (
              <div className={`notify-item ${item.read ? 'is-read' : ''}`} key={item.id}>
                <span className="notify-dot" />
                <span className="notify-body">
                  <span className="notify-title">{item.title}</span>
                  <span className="notify-time">{item.time}</span>
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="earnings-strip">
        <div>
          <TrendingUp size={22} />
          <div>
            <span>This week&apos;s earnings</span>
            <strong>${Math.round(revenue * 1.4)}</strong>
          </div>
        </div>
        <div>
          <Star size={22} />
          <div>
            <span>Account rating</span>
            <strong>4.8 / 5.0</strong>
          </div>
        </div>
        <div>
          <BadgeCheck size={22} />
          <div>
            <span>Protection status</span>
            <strong>Insurance active</strong>
          </div>
        </div>
      </section>
    </div>
  )
}
