import { useMemo, useState } from 'react'
import { Search, ShieldCheck, Sparkles, Zap } from 'lucide-react'
import AccountCard from '../components/AccountCard'
import { CATEGORIES } from '../data'
import { useStore } from '../store'

const SORTS = [
  { id: 'default', label: 'Recommended' },
  { id: 'price', label: 'Lowest price' },
  { id: 'rating', label: 'Top rated' },
  { id: 'rents', label: 'Most rented' },
]

export default function MarketplacePage() {
  const { accounts } = useStore()
  const [category, setCategory] = useState('all')
  const [sort, setSort] = useState('default')
  const [query, setQuery] = useState('')

  const list = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    const filtered = accounts.filter((account) => {
      const matchCategory = category === 'all' || account.platform === category
      if (!matchCategory) return false
      if (!keyword) return true
      const haystack = [
        account.title,
        account.subtitle,
        account.owner,
        ...account.tags,
        ...account.games,
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
    const sorted = [...filtered]
    if (sort === 'price') {
      sorted.sort((a, b) => a.priceHour - b.priceHour)
    } else if (sort === 'rating') {
      sorted.sort((a, b) => b.rating - a.rating)
    } else if (sort === 'rents') {
      sorted.sort((a, b) => b.rentCount - a.rentCount)
    } else {
      sorted.sort((a, b) => Number(b.featured) - Number(a.featured) || b.rentCount - a.rentCount)
    }
    return sorted
  }, [accounts, category, query, sort])

  const onlineCount = accounts.filter((item) => item.status === 'online').length

  return (
    <div className="market-page">
      <section className="market-hero">
        <img src="/assets/covers/hero-social.jpg" alt="" className="hero-bg" />
        <div className="hero-overlay" />
        <div className="hero-inner">
          <div className="hero-copy">
            <div className="eyebrow light">Renter marketplace</div>
            <h1>RentPass</h1>
            <p>Tinder · Bumble · Hinge · Instagram · Facebook · LinkedIn</p>
            <div className="hero-search">
              <Search size={19} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search accounts, interests or tags"
              />
              {query && (
                <button className="text-btn" onClick={() => setQuery('')}>
                  Clear
                </button>
              )}
            </div>
          </div>
          <div className="hero-stats">
            <div>
              <strong>{accounts.length}</strong>
              <span>Accounts live</span>
            </div>
            <div>
              <strong>{onlineCount}</strong>
              <span>Ready to go</span>
            </div>
            <div>
              <strong>99.2%</strong>
              <span>Order completion</span>
            </div>
            <div>
              <strong>24h</strong>
              <span>Risk response</span>
            </div>
          </div>
        </div>
      </section>

      <div className="market-toolbar">
        <div className="category-row">
          {CATEGORIES.map((item) => (
            <button
              key={item.id}
              className={category === item.id ? 'chip active' : 'chip'}
              onClick={() => setCategory(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="sort-row">
          {SORTS.map((item) => (
            <button
              key={item.id}
              className={sort === item.id ? 'sort-btn active' : 'sort-btn'}
              onClick={() => setSort(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <section className="market-list">
        <div className="section-head">
          <div>
            <div className="eyebrow">Marketplace</div>
            <h2>{category === 'all' ? 'All accounts' : CATEGORIES.find((c) => c.id === category)?.label}</h2>
          </div>
          <span className="result-count">{list.length} accounts</span>
        </div>

        {list.length ? (
          <div className="account-grid">
            {list.map((account) => (
              <AccountCard key={account.id} account={account} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Sparkles size={28} />
            <h3>No matching accounts</h3>
            <p>Try another keyword or category.</p>
          </div>
        )}
      </section>

      <section className="trust-strip">
        <div>
          <ShieldCheck size={20} />
          <strong>Account insurance</strong>
          <span>Bans covered first</span>
        </div>
        <div>
          <Zap size={20} />
          <strong>Instant handoff</strong>
          <span>Credentials auto-issued</span>
        </div>
        <div>
          <Sparkles size={20} />
          <strong>Human verification</strong>
          <span>Real-time alerts</span>
        </div>
      </section>
    </div>
  )
}
