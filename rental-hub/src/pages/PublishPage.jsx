import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  CalendarDays,
  Clock3,
  ImagePlus,
  Save,
  ShieldCheck,
  Tag,
  Wallet,
} from 'lucide-react'
import { fallbackCover, PLATFORM_META } from '../data'
import { useStore } from '../store'

const PLATFORM_IDS = Object.keys(PLATFORM_META)

export default function PublishPage() {
  const navigate = useNavigate()
  const { publishAccount } = useStore()
  const [cover, setCover] = useState('')
  const [form, setForm] = useState({
    platform: 'tinder',
    title: '',
    subtitle: '',
    description: '',
    priceHour: '',
    priceDay: '',
    stock: '1',
    deposit: '',
    tier: 'B',
    tags: '',
    games: '',
    features: '',
    insured: true,
    agree: false,
  })
  const [error, setError] = useState('')

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleCover = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    setCover(url)
  }

  const splitList = (value) =>
    value
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean)

  const submit = (event) => {
    event.preventDefault()
    if (!form.title.trim()) {
      setError('Please enter an account title')
      return
    }
    if (!form.priceHour || Number(form.priceHour) <= 0) {
      setError('Enter a valid hourly price')
      return
    }
    if (!form.agree) {
      setError('Agree to the platform terms first')
      return
    }
    setError('')
    publishAccount({
      platform: form.platform,
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      description: form.description.trim(),
      priceHour: Number(form.priceHour),
      priceDay: Number(form.priceDay) || Number(form.priceHour) * 8,
      stock: Number(form.stock) || 1,
      deposit: Number(form.deposit) || 0,
      tier: form.tier,
      tags: splitList(form.tags),
      games: splitList(form.games),
      features: splitList(form.features).length ? splitList(form.features) : ['Instant handoff'],
      insured: form.insured,
      cover: cover || fallbackCover[form.platform],
    })
    navigate('/owner')
  }

  const previewImage = cover || fallbackCover[form.platform]

  return (
    <div className="publish-page">
      <button className="back-link" onClick={() => navigate('/owner')}>
        <ArrowLeft size={17} />
        Back
      </button>

      <div className="page-head">
        <div>
          <div className="eyebrow">Publish</div>
          <h1>List an account</h1>
        </div>
        <span className="verified">
          <BadgeCheck size={16} />
          Identity verified
        </span>
      </div>

      <form className="publish-form" onSubmit={submit}>
        <div className="publish-layout">
          <div className="publish-main">
            <section className="form-section">
              <div className="form-section-title">
                <span>01</span>
                <div>
                  <h2>Basics</h2>
                  <p>Shown in marketplace and search</p>
                </div>
              </div>
              <div className="form-grid two">
                <div className="form-field">
                  <label>Platform</label>
                  <select value={form.platform} onChange={(event) => update('platform', event.target.value)}>
                    {PLATFORM_IDS.map((id) => (
                      <option value={id} key={id}>
                        {PLATFORM_META[id].name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label>Tier</label>
                  <select value={form.tier} onChange={(event) => update('tier', event.target.value)}>
                    <option value="S">S · Premium</option>
                    <option value="A">A · Featured</option>
                    <option value="B">B · Standard</option>
                  </select>
                </div>
                <div className="form-field span-2">
                  <label>Account title</label>
                  <input
                    value={form.title}
                    maxLength={30}
                    placeholder="e.g. Tinder Gold with active boost"
                    onChange={(event) => update('title', event.target.value)}
                  />
                </div>
                <div className="form-field span-2">
                  <label>One-line highlight</label>
                  <input
                    value={form.subtitle}
                    maxLength={60}
                    placeholder="e.g. Verified photos · High response"
                    onChange={(event) => update('subtitle', event.target.value)}
                  />
                </div>
                <div className="form-field span-2">
                  <label>Account description</label>
                  <textarea
                    value={form.description}
                    rows={4}
                    placeholder="Describe profile value, match history, usage limits, etc."
                    onChange={(event) => update('description', event.target.value)}
                  />
                </div>
              </div>
            </section>

            <section className="form-section">
              <div className="form-section-title">
                <span>02</span>
                <div>
                  <h2>Pricing & stock</h2>
                  <p>Hourly price drives default sorting</p>
                </div>
              </div>
              <div className="form-grid two">
                <div className="form-field">
                  <label>Hourly price</label>
                  <div className="input-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      min="0.1"
                      step="0.1"
                      value={form.priceHour}
                      placeholder="4"
                      onChange={(event) => update('priceHour', event.target.value)}
                    />
                  </div>
                </div>
                <div className="form-field">
                  <label>Daily price</label>
                  <div className="input-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      min="0.1"
                      step="0.1"
                      value={form.priceDay}
                      placeholder="28"
                      onChange={(event) => update('priceDay', event.target.value)}
                    />
                  </div>
                </div>
                <div className="form-field">
                  <label>Stock quantity</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    value={form.stock}
                    onChange={(event) => update('stock', event.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label>Deposit (hold)</label>
                  <div className="input-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      min="0"
                      step="10"
                      value={form.deposit}
                      placeholder="0"
                      onChange={(event) => update('deposit', event.target.value)}
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className="form-section">
              <div className="form-section-title">
                <span>03</span>
                <div>
                  <h2>Highlights & protection</h2>
                  <p>Tags appear on the marketplace card</p>
                </div>
              </div>
              <div className="form-grid">
                <div className="form-field">
                  <label>
                    <Tag size={15} />
                    Tags (comma separated)
                  </label>
                  <input
                    value={form.tags}
                    placeholder="verified, boost, high response"
                    onChange={(event) => update('tags', event.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label>Interests</label>
                  <input
                    value={form.games}
                    placeholder="dating, tinder, openers"
                    onChange={(event) => update('games', event.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label>Service highlights</label>
                  <input
                    value={form.features}
                    placeholder="instant login, fast handoff"
                    onChange={(event) => update('features', event.target.value)}
                  />
                </div>
              </div>
              <div className="form-options">
                <label className="check-line">
                  <input
                    type="checkbox"
                    checked={form.insured}
                    onChange={(event) => update('insured', event.target.checked)}
                  />
                  <span>Enable platform account insurance</span>
                </label>
                <label className="check-line">
                  <input
                    type="checkbox"
                    checked={form.agree}
                    onChange={(event) => update('agree', event.target.checked)}
                  />
                  <span>I agree to the Account Rental Agreement and Platform Risk Rules</span>
                </label>
              </div>
            </section>
          </div>

          <aside className="publish-side">
            <section className="form-section">
              <div className="form-section-title">
                <span>Cover</span>
                <div>
                  <h2>Account cover</h2>
                  <p>4:3 landscape recommended</p>
                </div>
              </div>
              <div className="cover-upload">
                <img src={previewImage} alt="" />
                <div className="cover-upload-actions">
                  <label className="primary-btn compact">
                    <ImagePlus size={16} />
                    Upload cover
                    <input type="file" accept="image/*" hidden onChange={handleCover} />
                  </label>
                  {cover && (
                    <button className="ghost-btn" onClick={() => setCover('')}>
                      Use default image
                    </button>
                  )}
                </div>
              </div>
            </section>

            <section className="publish-summary">
              <div className="summary-line">
                <span>Hourly rate</span>
                <strong>{form.priceHour ? `$${form.priceHour}` : 'Not set'}</strong>
              </div>
              <div className="summary-line">
                <span>Daily rate</span>
                <strong>
                  {form.priceDay ? `$${form.priceDay}` : form.priceHour ? `$${Number(form.priceHour) * 8}` : 'Not set'}
                </strong>
              </div>
              <div className="summary-line">
                <span>Stock</span>
                <strong>{form.stock || 0} unit(s)</strong>
              </div>
              <div className="summary-line">
                <span>Deposit</span>
                <strong>{form.deposit ? `$${form.deposit}` : 'No deposit'}</strong>
              </div>
              <div className="summary-icons">
                <span>
                  <Clock3 size={15} />
                  Instant handoff
                </span>
                <span>
                  <CalendarDays size={15} />
                  Hourly / daily
                </span>
                <span>
                  <ShieldCheck size={15} />
                  Platform protection
                </span>
                <span>
                  <Wallet size={15} />
                  Auto payout
                </span>
              </div>
            </section>

            {error && <div className="form-error">{error}</div>}

            <button className="primary-btn full" type="submit">
              <Save size={17} />
              Publish account
            </button>
          </aside>
        </div>
      </form>
    </div>
  )
}
