import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  CreditCard,
  KeyRound,
  QrCode,
  ShieldCheck,
  Wallet,
  X,
} from 'lucide-react'
import { formatPrice, makeId } from '../data'
import { useStore } from '../store'

export default function CheckoutModal({ account, onClose }) {
  const { rentAccount } = useStore()
  const [mode, setMode] = useState('hours')
  const [units, setUnits] = useState(3)
  const [pay, setPay] = useState('alipay')
  const [agree, setAgree] = useState(false)
  const [done, setDone] = useState(false)

  const unitPrice = mode === 'hours' ? account.priceHour : account.priceDay
  const total = useMemo(
    () => Math.round(unitPrice * units * 10) / 10,
    [unitPrice, units],
  )
  const remainingMin = mode === 'hours' ? units * 60 : units * 24 * 60

  const changeUnit = (delta) => {
    setUnits((value) => {
      const max = mode === 'hours' ? 48 : 30
      return Math.min(max, Math.max(1, value + delta))
    })
  }

  const confirm = () => {
    if (!agree) return
    rentAccount({
      accountId: account.id,
      mode,
      units,
      amount: total,
      startLabel: 'Just now',
      remainingMin,
    })
    setDone(true)
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="checkout-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button className="modal-close icon-btn" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        {!done ? (
          <>
            <div className="checkout-head">
              <div className="eyebrow">Rental checkout</div>
              <h2>{account.title}</h2>
              <p>{account.subtitle}</p>
            </div>

            <div className="checkout-body">
              <div className="form-field">
                <label>Rental length</label>
                <div className="segmented wide">
                  <button
                    className={mode === 'hours' ? 'active' : ''}
                    onClick={() => {
                      setMode('hours')
                      setUnits(3)
                    }}
                  >
                    <Clock3 size={16} />
                    Hourly
                  </button>
                  <button
                    className={mode === 'days' ? 'active' : ''}
                    onClick={() => {
                      setMode('days')
                      setUnits(1)
                    }}
                  >
                    <CalendarDays size={16} />
                    Daily
                  </button>
                </div>
              </div>

              <div className="form-field">
                <label>{mode === 'hours' ? 'Hours' : 'Days'}</label>
                <div className="stepper">
                  <button onClick={() => changeUnit(-1)}>-</button>
                  <span>{units} {mode === 'hours' ? 'hours' : 'days'}</span>
                  <button onClick={() => changeUnit(1)}>+</button>
                </div>
              </div>

              <div className="form-field">
                <label>Payment method</label>
                <div className="pay-options">
                  <button
                    className={pay === 'alipay' ? 'active' : ''}
                    onClick={() => setPay('alipay')}
                  >
                    <CreditCard size={18} />
                    Card
                  </button>
                  <button
                    className={pay === 'wechat' ? 'active' : ''}
                    onClick={() => setPay('wechat')}
                  >
                    <QrCode size={18} />
                    PayPal
                  </button>
                  <button
                    className={pay === 'wallet' ? 'active' : ''}
                    onClick={() => setPay('wallet')}
                  >
                    <Wallet size={18} />
                    Balance
                  </button>
                </div>
              </div>

              <div className="checkout-summary">
                <div className="summary-line">
                  <span>Unit price</span>
                  <strong>{formatPrice(unitPrice)} / {mode === 'hours' ? 'hr' : 'day'}</strong>
                </div>
                <div className="summary-line">
                  <span>Duration</span>
                  <strong>{units} {mode === 'hours' ? 'hours' : 'days'}</strong>
                </div>
                {account.deposit > 0 && (
                  <div className="summary-line">
                    <span>Deposit hold</span>
                    <strong>{formatPrice(account.deposit)}</strong>
                  </div>
                )}
                <div className="summary-line total">
                  <span>Total due</span>
                  <strong>{formatPrice(total)}</strong>
                </div>
              </div>

              <label className="check-line">
                <input
                  type="checkbox"
                  checked={agree}
                  onChange={(event) => setAgree(event.target.checked)}
                />
                <span>
                  I have read and agree to the Rental Agreement and Account Insurance Terms.
                </span>
              </label>
            </div>

            <div className="checkout-foot">
              <button className="primary-btn full" disabled={!agree} onClick={confirm}>
                <ShieldCheck size={18} />
                Pay {formatPrice(total)}
              </button>
            </div>
          </>
        ) : (
          <div className="checkout-success">
            <span className="success-icon">
              <CheckCircle2 size={34} />
            </span>
            <div className="eyebrow">Payment successful</div>
            <h2>Rental started</h2>
            <p>Login credentials were issued automatically. Find them in your order details.</p>
            <div className="credential-box">
              <KeyRound size={18} />
              <div>
                <span>Login credential</span>
                <strong>ZH-{makeId('cred').slice(-8).toUpperCase()}</strong>
              </div>
            </div>
            <div className="success-actions">
              <Link to="/rentals" className="primary-btn full" onClick={onClose}>
                View my rentals
              </Link>
              <button className="ghost-btn full" onClick={onClose}>
                Keep browsing
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
