import { useState } from 'react'
import { Check, Copy, KeyRound, Mail, X } from 'lucide-react'

function CopyButton({ value, label, onCopied, icon }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
      onCopied?.('已复制')
    } catch {
      onCopied?.('复制失败，请手动复制', 'error')
    }
  }
  return (
    <button className="btn btn-ghost cred-copy" onClick={copy} type="button">
      {copied ? <Check size={14} /> : icon}
      {copied ? '已复制' : label}
    </button>
  )
}

export default function CredentialsModal({ creds, onClose, onToast }) {
  const list = Array.isArray(creds) ? creds : [creds]
  const copyAll = async () => {
    const text = list.map((item) => `${item.address} : ${item.password}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      onToast?.(`已复制 ${list.length} 个账号密码`)
    } catch {
      onToast?.('复制失败，请手动复制', 'error')
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal cred-modal">
        <header className="modal-head">
          <div>
            <h3>邮箱已生成</h3>
            <small>请保存账号和密码，密码只会显示这一次</small>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="关闭"><X size={18} /></button>
        </header>
        <div className="cred-body">
          <div className="cred-hero">
            <span className="cred-hero-icon"><Mail size={22} /></span>
            <p>共生成 {list.length} 个邮箱，7 天后自动过期销毁。</p>
          </div>
          <div className="cred-list">
            {list.map((item, index) => (
              <div key={item.address} className="cred-item">
                <div className="cred-index">{index + 1}</div>
                <div className="cred-item-main">
                  <span className="cred-label"><Mail size={13} /> 账号</span>
                  <code>{item.address}</code>
                  <span className="cred-label"><KeyRound size={13} /> 密码</span>
                  <code>{item.password}</code>
                </div>
                <div className="cred-item-actions">
                  <CopyButton value={item.address} label="复制账号" icon={<Mail size={14} />} onCopied={onToast} />
                  <CopyButton value={item.password} label="复制密码" icon={<KeyRound size={14} />} onCopied={onToast} />
                  <CopyButton
                    value={`${item.address} : ${item.password}`}
                    label="复制账号密码"
                    icon={<Copy size={14} />}
                    onCopied={onToast}
                  />
                </div>
              </div>
            ))}
          </div>
          {list.length > 1 && (
            <button className="btn btn-ghost copy-all-btn" onClick={copyAll} type="button">
              <Copy size={15} /> 一键复制全部账号密码
            </button>
          )}
          <div className="cred-warning">
            密码使用不可逆加密保存，关闭这个窗口后就无法再次查看。你可以用账号和密码从任何设备重新登录。
          </div>
        </div>
        <footer className="modal-foot">
          <span className="spacer" />
          <button className="btn btn-primary" onClick={onClose} type="button">知道了</button>
        </footer>
      </div>
    </div>
  )
}
