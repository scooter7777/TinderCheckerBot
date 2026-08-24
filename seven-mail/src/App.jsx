import { useCallback, useEffect, useMemo, useState } from 'react'
import { Mail, Plus } from 'lucide-react'
import { api } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import LoginPage from './components/LoginPage.jsx'
import GeneratorPanel from './components/GeneratorPanel.jsx'
import MailboxView from './components/MailboxView.jsx'
import ComposeModal from './components/ComposeModal.jsx'
import CredentialsModal from './components/CredentialsModal.jsx'
import ToastStack from './components/ToastStack.jsx'

const SESSION_KEY = 'seven-mail-sessions'
const ADMIN_KEY = 'seven-mail-admin-token'

export default function App() {
  const [config, setConfig] = useState(null)
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [mailboxInfo, setMailboxInfo] = useState(null)
  const [messages, setMessages] = useState({ items: [], unread: 0, loading: false, error: '' })
  const [tab, setTab] = useState('inbox')
  const [selectedMsg, setSelectedMsg] = useState(null)
  const [compose, setCompose] = useState(null)
  const [toasts, setToasts] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mobileView, setMobileView] = useState('list')
  const [generating, setGenerating] = useState(false)
  const [loginBusy, setLoginBusy] = useState(false)
  const [createdCreds, setCreatedCreds] = useState(null)
  const [nowTick, setNowTick] = useState(Date.now())
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem(ADMIN_KEY) || '')

  const toast = useCallback((message, type = 'success') => {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((prev) => [...prev, { id, message, type }])
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200)
  }, [])

  const selectedSession = useMemo(
    () => sessions.find((s) => s.id === selectedId) || null,
    [sessions, selectedId],
  )
  const isAdmin = Boolean(adminToken)

  const loadMailboxData = useCallback(async (session, showLoading = false) => {
    if (showLoading) setMessages((prev) => ({ ...prev, loading: true, error: '' }))
    try {
      const [info, data] = await Promise.all([
        api.mailbox(session.id, session.token),
        api.messages(session.id, session.token),
      ])
      setMailboxInfo(info.mailbox)
      setMessages({ items: data.messages, unread: data.unread, loading: false, error: '' })
      return data
    } catch (e) {
      setMessages((prev) => ({ ...prev, loading: false, error: e.message }))
      if (e.message.includes('过期') || e.message.includes('不存在')) {
        setSessions((prev) => prev.filter((s) => s.id !== session.id))
        setSelectedId((prev) => (prev === session.id ? null : prev))
      }
      throw e
    }
  }, [])

  const selectMailbox = useCallback(
    async (session) => {
      setSelectedId(session.id)
      setSelectedMsg(null)
      setMobileView('list')
      setSidebarOpen(false)
      setTab('inbox')
      try {
        await loadMailboxData(session, true)
      } catch {
        // handled inside loadMailboxData
      }
    },
    [loadMailboxData],
  )

  useEffect(() => {
    let cancelled = false
    api.config()
      .then((cfg) => {
        if (!cancelled) setConfig(cfg)
      })
      .catch((e) => toast(e.message, 'error'))

    try {
      const saved = JSON.parse(localStorage.getItem(SESSION_KEY) || '[]')
      const live = saved.filter((s) => s.expiresAt > Date.now())
      if (!cancelled) {
        setSessions(live)
        if (live.length) selectMailbox(live[0])
      }
    } catch {
      // ignore broken local storage
    }
    return () => {
      cancelled = true
    }
  }, [toast, selectMailbox])

  useEffect(() => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessions))
  }, [sessions])

  useEffect(() => {
    const timer = window.setInterval(() => setNowTick(Date.now()), 30000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!selectedId) return
    const timer = window.setInterval(() => {
      const session = sessions.find((s) => s.id === selectedId)
      if (!session) return
      setNowTick(Date.now())
      loadMailboxData(session).catch(() => {})
    }, 6000)
    return () => window.clearInterval(timer)
  }, [selectedId, sessions, loadMailboxData])

  const handleCreate = useCallback(
    async (prefix, count = 1) => {
      setGenerating(true)
      try {
        const createdList =
          count > 1
            ? (await api.createMailboxes(count, prefix, adminToken)).mailboxes
            : [await api.createMailbox(prefix, adminToken)]
        const newSessions = createdList.map((created) => ({
          id: created.id,
          address: created.address,
          token: created.token,
          expiresAt: created.expiresAt,
          createdAt: created.createdAt,
        }))
        setSessions((prev) => [...newSessions, ...prev])
        setCreatedCreds(createdList.map((created) => ({ address: created.address, password: created.password })))
        toast(`已生成 ${createdList.length} 个邮箱`)
        await selectMailbox(newSessions[0])
        return createdList
      } catch (e) {
        toast(e.message, 'error')
        throw e
      } finally {
        setGenerating(false)
      }
    },
    [toast, selectMailbox, adminToken],
  )

  const handleAdminLogin = useCallback(
    async (token) => {
      await api.verifyAdmin(token)
      sessionStorage.setItem(ADMIN_KEY, token)
      setAdminToken(token)
      toast('管理员已登录')
    },
    [toast],
  )

  const handleAdminLogout = useCallback(() => {
    sessionStorage.removeItem(ADMIN_KEY)
    setAdminToken('')
    setCreatedCreds(null)
    toast('已退出管理', 'info')
  }, [toast])

  const handleLogoutMailbox = useCallback(
    (session) => {
      setSessions((prev) => prev.filter((s) => s.id !== session.id))
      setSelectedId(null)
      setSelectedMsg(null)
      setMessages({ items: [], unread: 0, loading: false, error: '' })
      toast('已退出登录', 'info')
    },
    [toast],
  )

  const handleLogin = useCallback(
    async (address, password) => {
      setLoginBusy(true)
      try {
        const logged = await api.login(address, password)
        const session = {
          id: logged.id,
          address: logged.address,
          token: logged.token,
          expiresAt: logged.expiresAt,
          createdAt: logged.createdAt,
        }
        setSessions((prev) => [session, ...prev.filter((s) => s.id !== session.id)])
        toast('登录成功')
        await selectMailbox(session)
        return logged
      } catch (e) {
        toast(e.message, 'error')
        throw e
      } finally {
        setLoginBusy(false)
      }
    },
    [toast, selectMailbox],
  )

  const handleDestroy = useCallback(
    async (session) => {
      if (!window.confirm(`销毁 ${session.address} 后，里面所有邮件都会删除，确定吗？`)) return
      try {
        await api.destroyMailbox(session.id, session.token)
        setSessions((prev) => prev.filter((s) => s.id !== session.id))
        setSelectedId((prev) => (prev === session.id ? null : prev))
        setSelectedMsg(null)
        setMessages({ items: [], unread: 0, loading: false, error: '' })
        toast('邮箱已销毁')
      } catch (e) {
        toast(e.message, 'error')
      }
    },
    [toast],
  )

  const openMessage = useCallback(
    async (id) => {
      const session = sessions.find((s) => s.id === selectedId)
      if (!session) return
      setSelectedMsg({ id, detail: null })
      try {
        const detail = await api.message(session.id, session.token, id)
        setSelectedMsg({ id, detail })
        setMessages((prev) => ({
          ...prev,
          items: prev.items.map((m) => (m.id === id ? { ...m, read: true } : m)),
        }))
        if (window.innerWidth < 900) setMobileView('read')
      } catch (e) {
        toast(e.message, 'error')
        setSelectedMsg(null)
      }
    },
    [sessions, selectedId, toast],
  )

  const openCompose = useCallback((message = null) => {
    setCompose({ message })
  }, [])

  const handleSend = useCallback(
    async (payload) => {
      const session = sessions.find((s) => s.id === selectedId)
      if (!session) return
      await api.send(session.id, session.token, payload)
      setCompose(null)
      toast('邮件已发送')
      loadMailboxData(session, true).catch(() => {})
    },
    [sessions, selectedId, toast, loadMailboxData],
  )

  const visibleMessages = useMemo(() => {
    if (tab === 'sent') return messages.items.filter((m) => m.direction === 'outgoing')
    return messages.items.filter((m) => m.direction === 'incoming')
  }, [messages.items, tab])

  return (
    <div className={`app ${mobileView === 'read' ? 'reading' : ''}`}>
      <Sidebar
        config={config}
        sessions={sessions}
        selectedId={selectedId}
        onSelect={selectMailbox}
        onCreate={() => setSidebarOpen(false)}
        onDestroy={handleDestroy}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        admin={isAdmin}
      />

      <main className="main">
        {!selectedSession && !isAdmin ? (
          <LoginPage
            config={config}
            onLogin={handleLogin}
            onAdminLogin={handleAdminLogin}
            loginBusy={loginBusy}
          />
        ) : !selectedSession ? (
          <GeneratorPanel
            config={config}
            onGenerate={handleCreate}
            onAdminLogout={handleAdminLogout}
            busy={generating}
          />
        ) : (
          <MailboxView
            session={selectedSession}
            config={config}
            messages={{ items: visibleMessages, unread: messages.unread }}
            loading={messages.loading}
            error={messages.error}
            tab={tab}
            onTabChange={setTab}
            selectedMsg={selectedMsg}
            onOpenMessage={openMessage}
            onBackToList={() => setMobileView('list')}
            onCompose={() => openCompose()}
            onReply={(message) => openCompose(message)}
            onRefresh={() => loadMailboxData(selectedSession, true).catch(() => {})}
            onDestroy={() => handleDestroy(selectedSession)}
            onOpenSidebar={() => setSidebarOpen(true)}
            onLogout={() => handleLogoutMailbox(selectedSession)}
            onToast={toast}
            nowTick={nowTick}
          />
        )}
      </main>

      {selectedSession && (
        <button className="fab" onClick={() => openCompose()} title="写邮件" type="button">
          <Plus size={20} />
        </button>
      )}

      {compose && selectedSession && (
        <ComposeModal
          session={selectedSession}
          message={compose.message}
          onClose={() => setCompose(null)}
          onSend={handleSend}
          onToast={toast}
        />
      )}

      {createdCreds && (
        <CredentialsModal
          creds={createdCreds}
          onClose={() => setCreatedCreds(null)}
          onToast={toast}
        />
      )}

      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />
    </div>
  )
}
