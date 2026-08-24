import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  KeyRound,
  Mail,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useStore } from '../store'

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

export default function VerifyModal({ task, account, onClose }) {
  const { resolveTask } = useStore()
  const [step, setStep] = useState(0)
  const [seconds, setSeconds] = useState(task.deadlineMin * 60)
  const [sent, setSent] = useState(false)
  const [code, setCode] = useState('')
  const [securityChecks, setSecurityChecks] = useState({
    sessions: false,
    protection: false,
    safe: false,
  })

  const mockCode = '482016'

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSeconds((value) => Math.max(0, value - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  const isVerify = task.kind === 'verify'
  const securityDone = Object.values(securityChecks).every(Boolean)

  const finish = () => {
    resolveTask(task.id)
    onClose()
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="verify-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button className="modal-close icon-btn" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="verify-head">
          <span className={`verify-icon ${isVerify ? 'verify' : 'risk'}`}>
            {isVerify ? <KeyRound size={22} /> : <ShieldAlert size={22} />}
          </span>
          <div>
            <div className="eyebrow">Account security</div>
            <h2>{task.title}</h2>
            <p>{account?.title}</p>
          </div>
          <span className={`countdown-chip ${seconds < 600 ? 'urgent' : ''}`}>
            {formatClock(seconds)}
          </span>
        </div>

        {step === 0 && (
          <div className="verify-step">
            <div className="reason-box">
              <ShieldAlert size={18} />
              <div>
                <strong>Trigger</strong>
                <p>{task.reason}</p>
              </div>
            </div>
            <div className="verify-channel">
              <Mail size={17} />
              <span>Verification channel</span>
              <strong>{task.channel}</strong>
            </div>
            <div className="step-list">
              {task.steps.map((text, index) => (
                <div key={text} className="step-row">
                  <span>{index + 1}</span>
                  <p>{text}</p>
                </div>
              ))}
            </div>
            <button className="primary-btn full" onClick={() => setStep(1)}>
              Start verification
            </button>
          </div>
        )}

        {step === 1 && isVerify && (
          <div className="verify-step">
            <div className="code-send">
              <Mail size={18} />
              <div>
                <strong>Email code</strong>
                <p>Sent to hj***88@example.com</p>
              </div>
              <button className="ghost-btn" disabled={sent} onClick={() => setSent(true)}>
                {sent ? 'Sent' : 'Get code'}
              </button>
            </div>
            {sent && (
              <div className="mock-sms">
                <span>Demo code</span>
                <strong>{mockCode}</strong>
                <button className="text-btn" onClick={() => setCode(mockCode)}>
                  Fill
                </button>
              </div>
            )}
            <div className="code-input">
              <input
                value={code}
                maxLength={6}
                placeholder="6-digit code"
                onChange={(event) => setCode(event.target.value)}
              />
              <button
                className="primary-btn"
                disabled={code !== mockCode}
                onClick={() => setStep(2)}
              >
                Confirm
              </button>
            </div>
            <button className="ghost-btn full" onClick={() => setStep(0)}>
              Back
            </button>
          </div>
        )}

        {step === 1 && !isVerify && (
          <div className="verify-step">
            <div className="security-checks">
              {[
                { key: 'sessions', label: 'Closed abnormal login sessions' },
                { key: 'protection', label: 'Enabled login protection' },
                { key: 'safe', label: 'Confirmed account is safe' },
              ].map((item) => (
                <label className="check-line" key={item.key}>
                  <input
                    type="checkbox"
                    checked={securityChecks[item.key]}
                    onChange={(event) =>
                      setSecurityChecks((prev) => ({
                        ...prev,
                        [item.key]: event.target.checked,
                      }))
                    }
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
            <button
              className="primary-btn full"
              disabled={!securityDone}
              onClick={() => setStep(2)}
            >
              <ShieldCheck size={18} />
              Confirm account is safe
            </button>
            <button className="ghost-btn full" onClick={() => setStep(0)}>
              Back
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="verify-success">
            <span className="success-icon">
              <CheckCircle2 size={34} />
            </span>
            <div className="eyebrow">Completed</div>
            <h2>Account restored</h2>
            <p>Security status synced. This account can be rented again.</p>
            <button className="primary-btn full" onClick={finish}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
