import { useState } from 'react'
import { Clock, LogOut, Mail, Plus, Send, ShieldCheck, Sparkles } from 'lucide-react'

export default function GeneratorPanel({ config, onGenerate, onAdminLogout, busy }) {
  const [prefix, setPrefix] = useState('')
  const [customCount, setCustomCount] = useState(10)

  return (
    <div className="generator-wrap">
      <div className="generator-card">
        <span className="generator-icon"><Sparkles size={26} /></span>
        <h1>生成一个 7 天有效的邮箱</h1>
        <p className="generator-sub">无需注册，地址到期后自动销毁，每个邮箱都可以独立收发邮件。</p>
        <div className="generator-form">
          <div className="prefix-box">
            <input
              value={prefix}
              onChange={(e) => setPrefix(e.target.value)}
              placeholder="自定义前缀（可选）"
              maxLength={32}
              autoComplete="off"
            />
            <span className="at">@</span>
            <span className="domain">{config?.domain || 'your.domain'}</span>
          </div>
          <div className="gen-actions">
            {[1, 5, 10, 20, 50].map((n) => (
              <button
                key={n}
                className="btn btn-ghost gen-quick"
                disabled={busy}
                type="button"
                onClick={() => onGenerate(prefix, n)}
              >
                <Plus size={15} /> 生成 {n} 个
              </button>
            ))}
          </div>
          <div className="gen-custom">
            <input
              type="number"
              min="1"
              max="100"
              value={customCount}
              onChange={(e) => setCustomCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
            />
            <button className="btn btn-primary generate-btn" disabled={busy} type="button" onClick={() => onGenerate(prefix, customCount)}>
              <Plus size={17} /> {busy ? '生成中…' : `生成 ${customCount} 个`}
            </button>
          </div>
        </div>
        <div className="feature-row">
          <span><Send size={15} /> 可发信</span>
          <span><Mail size={15} /> 可收信</span>
          <span><Clock size={15} /> 7 天有效</span>
          <span><ShieldCheck size={15} /> 到期销毁</span>
        </div>
        <button className="link-btn login-toggle" onClick={onAdminLogout} type="button">
          <LogOut size={14} /> 退出管理
        </button>
      </div>
    </div>
  )
}
