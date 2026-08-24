import { useEffect, useRef, useState } from 'react'
import { FileText, Paperclip, Send, X } from 'lucide-react'
import { api } from '../api.js'
import { formatDateTime, quoteBody, textToHtml } from '../format.js'

export default function ComposeModal({ session, message, onClose, onSend, onToast }) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [attachments, setAttachments] = useState([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  useEffect(() => {
    if (!message) return
    setTo(message.fromAddress || '')
    setSubject(/^re:/i.test(message.subject || '') ? message.subject : `Re: ${message.subject || ''}`)
    const quoted = quoteBody(message.text)
    setBody(
      `\n\n---------- 原始邮件 ----------\n发件人: ${message.fromName || message.fromAddress}\n时间: ${formatDateTime(message.receivedAt)}\n主题: ${message.subject || ''}\n\n${quoted}`,
    )
  }, [message])

  const handleFiles = (event) => {
    const files = Array.from(event.target.files || [])
    for (const file of files) {
      const reader = new FileReader()
      reader.onload = () => {
        setAttachments((prev) => [
          ...prev,
          {
            name: file.name,
            type: file.type || 'application/octet-stream',
            size: file.size,
            base64: String(reader.result || '').split(',')[1] || '',
          },
        ])
      }
      reader.readAsDataURL(file)
    }
    event.target.value = ''
  }

  const submit = async () => {
    if (!to.trim()) {
      setError('请填写收件人')
      return
    }
    setSending(true)
    setError('')
    try {
      await onSend({
        to,
        subject,
        text: body,
        html: textToHtml(body),
        attachments: attachments.map((att) => ({
          filename: att.name,
          contentType: att.type,
          base64: att.base64,
        })),
      })
    } catch (e) {
      setError(e.message)
      setSending(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal compose-modal">
        <header className="modal-head">
          <div>
            <h3>{message ? '回复邮件' : '写邮件'}</h3>
            <small>发件人：{session.address}</small>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="关闭"><X size={18} /></button>
        </header>

        <div className="compose-fields">
          <div className="field-row">
            <label>收件人</label>
            <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@example.com" />
          </div>
          <div className="field-row">
            <label>主题</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="邮件主题" />
          </div>
          <textarea
            className="compose-body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="写下你想说的话…"
          />
          {attachments.length > 0 && (
            <div className="attachment-editor">
              {attachments.map((att, index) => (
                <span key={`${att.name}-${index}`} className="attachment-chip">
                  <FileText size={14} />
                  <span>{att.name}</span>
                  <button
                    className="chip-x"
                    onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== index))}
                    type="button"
                  >
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}
          {error && <div className="form-error">{error}</div>}
        </div>

        <footer className="modal-foot">
          <button className="btn btn-primary" onClick={submit} disabled={sending} type="button">
            <Send size={15} /> {sending ? '发送中…' : '发送'}
          </button>
          <button className="btn btn-ghost" onClick={() => fileRef.current?.click()} type="button">
            <Paperclip size={15} /> 添加附件
          </button>
          <span className="spacer" />
          <button className="btn btn-ghost" onClick={onClose} type="button">取消</button>
          <input ref={fileRef} type="file" multiple hidden onChange={handleFiles} />
        </footer>
      </div>
    </div>
  )
}
