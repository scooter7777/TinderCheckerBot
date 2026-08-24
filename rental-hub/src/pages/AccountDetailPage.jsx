import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  KeyRound,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
  Star,
  Users,
  Zap,
} from 'lucide-react'
import AccountCard from '../components/AccountCard'
import CheckoutModal from '../components/CheckoutModal'
import { formatPrice, PLATFORM_META } from '../data'
import { useStore } from '../store'

export default function AccountDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { accounts } = useStore()
  const [checkout, setCheckout] = useState(false)

  const account = accounts.find((item) => item.id === id)

  if (!account) {
    return (
      <div className="empty-state page-empty">
        <ShieldAlert size={30} />
        <h2>Account not found or delisted</h2>
        <button className="primary-btn" onClick={() => navigate('/')}>
          Back to marketplace
        </button>
      </div>
    )
  }

  const platform = PLATFORM_META[account.platform]
  const related = accounts
    .filter((item) => item.id !== account.id && item.platform === account.platform)
    .slice(0, 3)
  const relatedFull = related.length >= 3 ? related : accounts.filter((item) => item.id !== account.id).slice(0, 3)

  return (
    <div className="detail-page">
      <button className="back-link" onClick={() => navigate(-1)}>
        <ArrowLeft size={17} />
        Back to marketplace
      </button>

      <section className="detail-hero">
        <div className="detail-cover">
          <img src={account.image} alt="" />
          <span className="platform-chip" style={{ background: platform.color }}>
            {platform.name}
          </span>
          {account.badge && <span className="account-badge">{account.badge}</span>}
          <span className={`stock-pill ${account.status}`}>
            {account.status === 'risk' ? 'Verify now' : 'Available'}
          </span>
        </div>
        <div className="detail-copy">
          <div className="eyebrow">Account details</div>
          <h1>{account.title}</h1>
          <p className="detail-subtitle">{account.subtitle}</p>
          <div className="detail-tags">
            {account.tags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
          <div className="detail-meta-row">
            <span className="rating">
              <Star size={15} fill="currentColor" />
              {account.rating.toFixed(1)}
            </span>
            <span>{account.reviews} reviews</span>
            <span>{account.rentCount} rentals</span>
            <span className="verified">
              <BadgeCheck size={15} />
              {account.verified ? 'Verified' : 'Unverified'}
            </span>
          </div>
          <div className="owner-line">
            <span className="avatar small">
              <Users size={15} />
            </span>
            <div>
              <strong>{account.owner}</strong>
              <span>Platform verified host</span>
            </div>
            {account.insured && (
              <span className="insured-pill">
                <ShieldCheck size={14} />
                Platform insurance
              </span>
            )}
          </div>
        </div>
      </section>

      <div className="detail-layout">
        <div className="detail-main">
          {account.status === 'risk' && (
            <div className="risk-banner">
              <ShieldAlert size={20} />
              <div>
                <strong>Account is waiting for security review</strong>
                <p>It will return to available status as soon as verification is complete.</p>
              </div>
              <span className="stock-pill risk">In review</span>
            </div>
          )}

          <section className="detail-section">
            <h2>About this account</h2>
            <p className="detail-description">{account.description}</p>
          </section>

          <section className="detail-section">
            <h2>Key highlights</h2>
            <div className="feature-grid">
              {account.features.map((feature) => (
                <div className="feature-item" key={feature}>
                  <CheckCircle2 size={17} />
                  <span>{feature}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="detail-section">
            <h2>Account details</h2>
            <div className="spec-grid">
              {Object.entries(account.specs).map(([key, value]) => (
                <div className="spec-item" key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
              {account.games.length > 0 && (
                <div className="spec-item wide">
                  <span>Interests</span>
                  <strong>{account.games.join(' · ')}</strong>
                </div>
              )}
            </div>
          </section>

          <section className="detail-section">
            <h2>Rental protection</h2>
            <div className="guarantee-grid">
              <div>
                <LockKeyhole size={19} />
                <strong>Credential custody</strong>
                <span>Credentials are encrypted and held by the platform</span>
              </div>
              <div>
                <ShieldCheck size={19} />
                <strong>Account insurance</strong>
                <span>Bans and disputes covered first</span>
              </div>
              <div>
                <Zap size={19} />
                <strong>Instant alerts</strong>
                <span>Real-time verification and risk alerts</span>
              </div>
            </div>
          </section>
        </div>

        <aside className="rent-panel">
          <div className="rent-price">
            <span>{formatPrice(account.priceHour)}</span>
            <small>/hour</small>
          </div>
          <div className="rent-days">Day rate {formatPrice(account.priceDay)}</div>
          <div className="rent-options">
            <div>
              <Clock3 size={16} />
              <span>Hourly / Daily</span>
            </div>
            <div>
              <KeyRound size={16} />
              <span>Auto handoff</span>
            </div>
            <div>
              <Users size={16} />
              <span>{account.stock} in stock</span>
            </div>
          </div>
          {account.deposit > 0 && (
            <div className="deposit-line">
              Deposit {formatPrice(account.deposit)}, auto-released when the rental ends
            </div>
          )}
          <button
            className="primary-btn full rent-btn"
            disabled={account.status !== 'online' || account.stock <= 0}
            onClick={() => setCheckout(true)}
          >
            {account.status === 'risk' ? 'Available after verification' : `Rent now ${formatPrice(account.priceHour)}/hr`}
          </button>
          <p className="rent-note">
            <ShieldCheck size={14} />
            Platform insured · No-deposit whitelist · Instant handoff
          </p>
        </aside>
      </div>

      <section className="related-section">
        <div className="section-head">
          <div>
            <div className="eyebrow">You may also like</div>
            <h2>Related accounts</h2>
          </div>
        </div>
        <div className="account-grid">
          {relatedFull.map((item) => (
            <AccountCard key={item.id} account={item} />
          ))}
        </div>
      </section>

      {checkout && (
        <CheckoutModal account={account} onClose={() => setCheckout(false)} />
      )}
    </div>
  )
}
