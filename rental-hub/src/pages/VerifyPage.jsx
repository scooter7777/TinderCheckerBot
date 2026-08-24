import { useState } from 'react'
import {
  CheckCircle2,
  Clock3,
  FlaskConical,
  KeyRound,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import VerifyModal from '../components/VerifyModal'
import { useStore } from '../store'

export default function VerifyPage() {
  const { tasks, accounts, notifications, simulateEvent } = useStore()
  const [selected, setSelected] = useState(null)

  const accountById = (id) => accounts.find((item) => item.id === id)
  const resolved = notifications.filter(
    (item) =>
      item.type === 'system' &&
      (item.title.includes('completed') || item.title.includes('cleared')),
  )

  return (
    <div className="verify-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Security Center</div>
          <h1>Verify center</h1>
        </div>
        <button className="ghost-btn" onClick={simulateEvent}>
          <FlaskConical size={16} />
          Simulate security event
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-tile red">
          <span className="stat-icon">
            <ShieldAlert size={19} />
          </span>
          <div>
            <strong>{tasks.length}</strong>
            <span>Open alerts</span>
          </div>
        </div>
        <div className="stat-tile lime">
          <span className="stat-icon">
            <CheckCircle2 size={19} />
          </span>
          <div>
            <strong>{resolved.length}</strong>
            <span>Completed this month</span>
          </div>
        </div>
        <div className="stat-tile cyan">
          <span className="stat-icon">
            <Zap size={19} />
          </span>
          <div>
            <strong>26 min</strong>
            <span>Average handling time</span>
          </div>
        </div>
        <div className="stat-tile orange">
          <span className="stat-icon">
            <Clock3 size={19} />
          </span>
          <div>
            <strong>24h</strong>
            <span>Risk monitoring</span>
          </div>
        </div>
      </div>

      <section className="dashboard-section">
        <div className="section-head">
          <div>
            <div className="eyebrow">Pending</div>
            <h2>Accounts to handle</h2>
          </div>
          <span className="result-count">{tasks.length} events</span>
        </div>

        {tasks.length ? (
          <div className="task-card-grid">
            {tasks.map((task) => {
              const account = accountById(task.accountId)
              const isVerify = task.kind === 'verify'
              return (
                <div className="task-card" key={task.id}>
                  <div className="task-card-top">
                    <img src={account.image} alt="" />
                    <span className={`task-kind ${task.kind}`}>
                      {isVerify ? <KeyRound size={18} /> : <ShieldAlert size={18} />}
                    </span>
                    <span className={`countdown-chip ${task.deadlineMin < 30 ? 'urgent' : ''}`}>
                      {task.deadlineMin} min left
                    </span>
                  </div>
                  <div className="task-card-body">
                    <span className="task-type-label">{isVerify ? 'Human verification' : 'Ban risk'}</span>
                    <h3>{account.title}</h3>
                    <p>{task.reason}</p>
                    <div className="mini-steps">
                      {task.steps.map((step, index) => (
                        <div key={step}>
                          <span>{index + 1}</span>
                          <p>{step}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="task-card-foot">
                    <span className="verify-channel">
                      <ShieldCheck size={14} />
                      {task.channel}
                    </span>
                    <button className="primary-btn compact" onClick={() => setSelected(task)}>
                      Start verification
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="empty-state">
            <ShieldCheck size={30} />
            <h3>All accounts look good</h3>
            <p>You will be notified instantly when verification or risk events come in.</p>
            <button className="ghost-btn" onClick={simulateEvent}>
              Simulate an event
            </button>
          </div>
        )}
      </section>

      {selected && (
        <VerifyModal
          task={selected}
          account={accountById(selected.accountId)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
