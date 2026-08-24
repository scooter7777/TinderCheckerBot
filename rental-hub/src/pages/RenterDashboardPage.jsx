import { Link } from 'react-router-dom'
import {
  CheckCircle2,
  Clock3,
  KeyRound,
  PackageOpen,
  Wallet,
} from 'lucide-react'
import { formatPrice } from '../data'
import { useStore } from '../store'

function OrderRow({ order, account }) {
  return (
    <div className="order-row">
      <img src={account.image} alt="" />
      <div className="order-info">
        <div className="order-title-line">
          <strong>{account.title}</strong>
          <span className={`order-status ${order.status}`}>
            {order.status === 'active' ? 'Active' : order.status === 'scheduled' ? 'Scheduled' : 'Completed'}
          </span>
        </div>
        <span className="order-sub">
          {order.mode === 'hours' ? `${order.units} hours` : `${order.units} days`}
          {' · '}
          {order.started}
        </span>
      </div>
      <div className="order-amount">{formatPrice(order.amount)}</div>
      {order.status === 'active' && (
        <div className="order-remaining">
          <Clock3 size={15} />
          {Math.floor(order.remainingMin / 60)}h {order.remainingMin % 60}m left
        </div>
      )}
      <div className="order-actions">
        {order.status === 'active' && (
          <Link to={`/account/${account.id}`} className="ghost-btn">
            Extend
          </Link>
        )}
        {order.status !== 'ended' && (
          <span className="credential-tag">
            <KeyRound size={13} />
            ZH-{order.id.slice(-6).toUpperCase()}
          </span>
        )}
      </div>
    </div>
  )
}

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

export default function RenterDashboardPage() {
  const { accounts, orders } = useStore()
  const accountById = (id) => accounts.find((item) => item.id === id)
  const activeOrders = orders.filter((item) => item.status === 'active')
  const historyOrders = orders.filter((item) => item.status !== 'active')
  const spent = orders
    .filter((item) => item.status !== 'canceled')
    .reduce((sum, item) => sum + item.amount, 0)
  const completed = orders.filter((item) => item.status === 'ended').length

  return (
    <div className="dashboard-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">My rentals</div>
          <h1>Renter dashboard</h1>
        </div>
        <Link to="/" className="primary-btn compact">
          Rent an account
        </Link>
      </div>

      <div className="stats-grid">
        <StatTile
          icon={<PackageOpen size={19} />}
          label="Active rentals"
          value={activeOrders.length}
          tone="cyan"
        />
        <StatTile
          icon={<Wallet size={19} />}
          label="Spent this month"
          value={`$${spent}`}
          tone="orange"
        />
        <StatTile
          icon={<CheckCircle2 size={19} />}
          label="Completed rentals"
          value={completed}
          tone="lime"
        />
        <StatTile
          icon={<Clock3 size={19} />}
          label="Active hours"
          value={activeOrders.reduce((sum, item) => sum + (item.mode === 'hours' ? item.units : item.units * 24), 0)}
          tone="blue"
        />
      </div>

      <section className="dashboard-section">
        <div className="section-head">
          <div>
            <div className="eyebrow">Rentals</div>
            <h2>Active</h2>
          </div>
          <Link to="/" className="ghost-btn">
            Go to marketplace
          </Link>
        </div>
        {activeOrders.length ? (
          <div className="order-list">
            {activeOrders.map((order) => (
              <OrderRow key={order.id} order={order} account={accountById(order.accountId)} />
            ))}
          </div>
        ) : (
          <div className="empty-state compact">
            <PackageOpen size={24} />
            <p>No active rentals</p>
            <Link to="/" className="primary-btn compact">
              Rent an account
            </Link>
          </div>
        )}
      </section>

      <section className="dashboard-section">
        <div className="section-head">
          <div>
            <div className="eyebrow">History</div>
            <h2>Order history</h2>
          </div>
        </div>
        {historyOrders.length ? (
          <div className="order-list">
            {historyOrders.map((order) => (
              <OrderRow key={order.id} order={order} account={accountById(order.accountId)} />
            ))}
          </div>
        ) : (
          <div className="empty-state compact">
            <p>No order history</p>
          </div>
        )}
      </section>
    </div>
  )
}
