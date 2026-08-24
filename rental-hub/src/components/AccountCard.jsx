import { Link } from 'react-router-dom'
import { BadgeCheck, Star } from 'lucide-react'
import { formatPrice, PLATFORM_META } from '../data'

export default function AccountCard({ account }) {
  const platform = PLATFORM_META[account.platform]

  return (
    <Link to={`/account/${account.id}`} className="account-card">
      <div className="account-cover">
        <img src={account.image} alt="" loading="lazy" />
        <span className="platform-chip" style={{ background: platform.color }}>
          {platform.name}
        </span>
        {account.badge && <span className="account-badge">{account.badge}</span>}
        <span className={`stock-pill ${account.status}`}>
          {account.status === 'risk' ? 'In review' : account.status === 'online' ? 'Available' : 'Rented'}
        </span>
      </div>
      <div className="account-info">
        <div className="account-title-row">
          <h3>{account.title}</h3>
          <span className="tier-badge">T{account.tier}</span>
        </div>
        <p className="account-subtitle">{account.subtitle}</p>
        <div className="account-tags">
          {account.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <div className="account-meta">
          <span className="rating">
            <Star size={14} fill="currentColor" />
            {account.rating.toFixed(1)}
          </span>
          <span>{account.rentCount} rentals</span>
          {account.verified && (
            <span className="verified">
              <BadgeCheck size={14} />
              Verified
            </span>
          )}
        </div>
        <div className="account-price-row">
          <span className="price">
            {formatPrice(account.priceHour)}
            <small>/hr</small>
          </span>
          <span className="day-price">Day {formatPrice(account.priceDay)}</span>
        </div>
      </div>
    </Link>
  )
}
