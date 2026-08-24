import { useState } from 'react'
import { KeyRound, Lock, LogIn, Mail, ShieldCheck, Sparkles } from 'lucide-react'

export default function LoginPage({ config, onLogin, onAdminLogin, loginBusy }) {
  const [address, setAddress] = useState('')
  const [password, setPassword] = useState('')
  const [adminMode, setAdminMode] = useState(false)
  const [adminPassword, setAdminPassword] = useState('')
  const [adminBusy, setAdminBusy] = useState(false)

  const submitLogin = async (event) => {
    event.preventDefault()
    try {
      await onLogin(address, password)
    } catch {
      // error toast handled by parent
    }
  }

  const submitAdmin = async (event) => {
    event.preventDefault()
    setAdminBusy(true)
    try {
      await onAdminLogin(adminPassword)
      setAdminPassword('')
      setAdminMode(false)
    } catch {
      // error toast handled by parent
    } finally {
      setAdminBusy(false)
    }
  }

  return (
    <div className="generator-wrap">
      <div className="login-card">
        <span className="generator-icon"><Mail size={26} /></span>
        <h1>登录你的临时邮箱</h1>
        <p className="generator-sub">输入生成时保存的账号和密码，查看 7 天内的收件。</p>

        {!adminMode ? (
          <>
            <form className="login-form" onSubmit={submitLogin}>
              <div className="login-field">
                <Mail size={15} />
                <input
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder={`账号（xxx@${config?.domain || 'your.domain'}）`}
                  autoComplete="username"
                />
              </div>
              <div className="login-field">
                <KeyRound size={15} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="密码"
                  autoComplete="current-password"
                />
              </div>
              <button className="btn btn-primary login-submit" disabled={loginBusy} type="submit">
                <LogIn size={15} /> {loginBusy ? '登录中…' : '登录'}
              </button>
            </form>
            <button className="link-btn admin-entry" onClick={() => setAdminMode(true)} type="button">
              <ShieldCheck size={14} /> 管理员入口
            </button>
          </>
        ) : (
          <form className="login-form" onSubmit={submitAdmin}>
            <div className="login-field">
              <Lock size={15} />
              <input
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                placeholder="管理员密码"
                autoComplete="current-password"
              />
            </div>
            <button className="btn btn-primary login-submit" disabled={adminBusy} type="submit">
              <ShieldCheck size={15} /> {adminBusy ? '验证中…' : '进入管理'}
            </button>
            <button className="link-btn admin-entry" onClick={() => setAdminMode(false)} type="button">
              <Sparkles size={14} /> 返回登录
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
