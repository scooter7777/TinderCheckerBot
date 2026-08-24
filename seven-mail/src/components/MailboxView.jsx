import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  Clock,
  Copy,
  FileText,
  Inbox,
  LogOut,
  Menu,
  Paperclip,
  RefreshCw,
  Reply,
  Send,
  Trash2,
} from 'lucide-react'
import { attachmentUrl } from '../api.js'
import {
  avatarColor,
  formatBytes,
  formatDateTime,
  formatRemaining,
  formatShortDate,
  initials,
} from '../format.js'

function resizeFrame(event) {
  try {
    const doc = event.currentTarget.contentDocument
    if (!doc?.body) return
    event.currentTarget.style.height = `${Math.max(280, Math.min(window.innerHeight * 0.78, doc.body.scrollHeight + 24))}px`
  } catch {
    // iframe cross-origin protections can block access; fixed height is fine
  }
}

export default function MailboxView({
  session,
  config,
  messages,
  loading,
  error,
  tab,
  onTabChange,
  selectedMsg,
  onOpenMessage,
  onBackToList,
  onCompose,
  onReply,
  onRefresh,
  onDestroy,
  onOpenSidebar,
  onLogout,
  onToast,
  nowTick,
}) {
  const [copied, setCopied] = useState(false)
  const visibleMessages = useMemo(() => {
    if (tab === 'sent') return messages.items.filter((m) => m.direction === 'outgoing')
    return messages.items.filter((m) => m.direction === 'incoming')
  }, [messages.items, tab])
  const unread = messages.items.filter((m) => m.direction === 'incoming' && !m.read).length
  const detail = selectedMsg?.detail

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(session.address)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      onToast('复制失败，请手动复制', 'error')
    }
  }

  const senderValue = (row) => (row.direction === 'incoming' ? row.fromAddress : row.toAddress)
  const senderName = (row) =>
    row.direction === 'incoming' ? row.fromName || row.fromAddress : `发给 ${row.toAddress}`

  return (
    <section className="mailbox-pane">
      <header className="mailbox-head">
        <div className="address-row">
          <button className="icon-btn mobile-only" onClick={onOpenSidebar} aria-label="邮箱列表">
            <Menu size={18} />
          </button>
          <div className="address-main">
            <h1>{session.address}</h1>
            <div className="address-meta">
              <span className="ttl-chip"><Clock size={13} /> 剩余 {formatRemaining(session.expiresAt - nowTick)}</span>
              <span className="provider-chip">
                {config?.provider === 'mailgun' ? 'Mailgun' : config?.provider === 'smtp' ? 'SMTP' : '演示模式'}
              </span>
            </div>
          </div>
          <div className="address-actions">
            <button className="btn btn-ghost" onClick={copyAddress} type="button">
              <Copy size={15} /> {copied ? '已复制' : '复制'}
            </button>
            <button className="icon-btn" onClick={onRefresh} title="刷新" type="button">
              <RefreshCw size={16} className={loading ? 'spin' : ''} />
            </button>
            <button className="btn btn-ghost" onClick={onLogout} type="button">
              <LogOut size={15} /> 退出登录
            </button>
            <button className="btn btn-ghost danger-ghost" onClick={onDestroy} type="button">
              <Trash2 size={15} /> 销毁
            </button>
          </div>
        </div>

        <div className="mailbox-tabs">
          <button className={tab === 'inbox' ? 'active' : ''} onClick={() => onTabChange('inbox')} type="button">
            收件箱 {unread > 0 && <span className="count">{unread}</span>}
          </button>
          <button className={tab === 'sent' ? 'active' : ''} onClick={() => onTabChange('sent')} type="button">
            已发送
          </button>
          <span className="spacer" />
          <button className="btn btn-primary compose-top" onClick={onCompose} type="button">
            <Send size={15} /> 写邮件
          </button>
        </div>
      </header>

      <div className="mailbox-body">
        <div className="message-list">
          {loading && visibleMessages.length === 0 ? (
            <div className="skeleton-list">
              {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton-row" />)}
            </div>
          ) : error ? (
            <div className="pane-empty">
              <Inbox size={30} />
              <p>{error}</p>
              <button className="btn btn-ghost" onClick={onRefresh} type="button"><RefreshCw size={14} /> 重试</button>
            </div>
          ) : visibleMessages.length === 0 ? (
            <div className="pane-empty">
              <Inbox size={30} />
              <p>{tab === 'sent' ? '还没有发送过邮件' : '还没有收到邮件，等一会儿会自动刷新'}</p>
            </div>
          ) : (
            visibleMessages.map((row) => (
              <article
                key={row.id}
                className={`msg-row ${row.read ? '' : 'unread'} ${row.id === selectedMsg?.id ? 'selected' : ''}`}
                onClick={() => onOpenMessage(row.id)}
              >
                <span className="msg-avatar" style={{ background: avatarColor(senderValue(row)) }}>
                  {initials(senderValue(row))}
                </span>
                <div className="msg-content">
                  <div className="msg-top">
                    <strong>{senderName(row)}</strong>
                    <time>{formatShortDate(row.receivedAt)}</time>
                  </div>
                  <div className="msg-subject">{row.subject}</div>
                  <div className="msg-snippet">{row.snippet || '（无正文）'}</div>
                </div>
                {row.attachmentCount > 0 && <Paperclip size={14} className="msg-pin" />}
              </article>
            ))
          )}
        </div>

        <div className="message-reader">
          {!selectedMsg && (
            <div className="reader-empty">
              <span className="reader-empty-icon"><Mail2 /></span>
              <p>选择一封邮件查看内容</p>
            </div>
          )}
          {selectedMsg && !detail && (
            <div className="reader-loading">
              <div className="spinner" />
              <p>正在读取邮件…</p>
            </div>
          )}
          {detail && (
            <div className="reader-content">
              <div className="reader-head">
                <button className="icon-btn mobile-only" onClick={onBackToList} aria-label="返回列表">
                  <ArrowLeft size={18} />
                </button>
                <h2>{detail.subject || '(无主题)'}</h2>
                <div className="reader-actions">
                  {detail.direction === 'incoming' && (
                    <button className="btn btn-ghost" onClick={() => onReply(detail)} type="button">
                      <Reply size={15} /> 回复
                    </button>
                  )}
                </div>
              </div>
              <div className="reader-meta">
                <span
                  className="avatar large"
                  style={{ background: avatarColor(detail.direction === 'incoming' ? detail.fromAddress : detail.toAddress) }}
                >
                  {initials(detail.direction === 'incoming' ? detail.fromAddress : detail.toAddress)}
                </span>
                <div className="reader-sender">
                  <strong>{detail.direction === 'incoming' ? detail.fromName || detail.fromAddress : '我'}</strong>
                  <span>{detail.direction === 'incoming' ? detail.fromAddress : `发给 ${detail.toAddress}`}</span>
                </div>
                <time>{formatDateTime(detail.receivedAt)}</time>
              </div>
              <div className="reader-body">
                {detail.html ? (
                  <iframe
                    title="邮件内容"
                    sandbox="allow-popups allow-same-origin"
                    referrerPolicy="no-referrer"
                    srcDoc={detail.html}
                    onLoad={resizeFrame}
                    className="email-html"
                  />
                ) : (
                  <div className="email-text">{detail.text || '（无正文）'}</div>
                )}
              </div>
              {detail.attachments?.length > 0 && (
                <div className="attachments">
                  <div className="attachments-title">附件（{detail.attachments.length}）</div>
                  {detail.attachments.map((att) => (
                    <a
                      key={att.index}
                      className="attachment-download"
                      href={attachmentUrl(session.id, session.token, detail.id, att.index)}
                      download
                    >
                      <span className="attachment-icon"><FileText size={16} /></span>
                      <span className="attachment-meta">
                        <strong>{att.filename}</strong>
                        <small>{formatBytes(att.size)} · 下载</small>
                      </span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function Mail2() {
  return <span className="reader-empty-mail">@</span>
}
