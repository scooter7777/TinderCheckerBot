import { Clock, Mail, Plus, Trash2, X } from 'lucide-react'
import { formatRemaining } from '../format.js'

export default function Sidebar({ config, sessions, selectedId, onSelect, onCreate, onDestroy, open, onClose, admin }) {
  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <div className="sidebar-head">
        <div className="brand">
          <span className="brand-icon"><Mail size={20} /></span>
          <span>
            <strong>七日邮箱</strong>
            <small>{config?.domain || '7 天临时邮箱'}</small>
          </span>
        </div>
        <button className="icon-btn sidebar-close" onClick={onClose} aria-label="关闭"><X size={18} /></button>
      </div>

      {admin && (
        <button className="btn btn-primary add-btn" onClick={onCreate}><Plus size={16} /> 生成新邮箱</button>
      )}

      <div className="session-list">
        <div className="section-label">我的邮箱（{sessions.length}）</div>
        {sessions.length === 0 && (
          <div className="sidebar-empty">还没有生成邮箱，点上面的按钮创建一个。</div>
        )}
        {sessions.map((session) => {
          const [local, domain] = session.address.split('@')
          const expired = session.expiresAt <= Date.now()
          return (
            <div
              key={session.id}
              className={`session-row ${session.id === selectedId ? 'active' : ''} ${expired ? 'expired' : ''}`}
              onClick={() => onSelect(session)}
              role="button"
            >
              <div className="session-main">
                <span className="session-address"><strong>{local}</strong>@{domain}</span>
                <span className={`session-ttl ${expired ? 'expired' : ''}`}>
                  <Clock size={11} /> {expired ? '已过期' : `剩余 ${formatRemaining(session.expiresAt - Date.now())}`}
                </span>
              </div>
              <button
                className="mini-btn danger"
                onClick={(e) => { e.stopPropagation(); onDestroy(session) }}
                title="销毁邮箱"
                type="button"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )
        })}
      </div>

      <div className="sidebar-foot">
        <span className="dot" /> 到期自动销毁 · 令牌仅保存在本机
      </div>
    </aside>
  )
}
