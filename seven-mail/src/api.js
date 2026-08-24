async function request(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) throw new Error(data?.error || `请求失败 (${res.status})`)
  return data
}

export const api = {
  config: () => request('/api/config'),
  createMailbox: (prefix, adminToken = '') =>
    request('/api/mailboxes', {
      method: 'POST',
      headers: adminToken ? { 'X-Admin-Token': adminToken } : {},
      body: JSON.stringify({ prefix: prefix || '' }),
    }),
  createMailboxes: (count, prefix, adminToken = '') =>
    request('/api/mailboxes/batch', {
      method: 'POST',
      headers: adminToken ? { 'X-Admin-Token': adminToken } : {},
      body: JSON.stringify({ count, prefix: prefix || '' }),
    }),
  verifyAdmin: (token) =>
    request('/api/admin/verify', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  login: (address, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ address, password }),
    }),
  mailbox: (id, token) => request(`/api/mailboxes/${id}?token=${encodeURIComponent(token)}`),
  destroyMailbox: (id, token) =>
    request(`/api/mailboxes/${id}?token=${encodeURIComponent(token)}`, { method: 'DELETE' }),
  messages: (id, token) => request(`/api/mailboxes/${id}/messages?token=${encodeURIComponent(token)}`),
  message: (id, token, mid) =>
    request(`/api/mailboxes/${id}/messages/${mid}?token=${encodeURIComponent(token)}`),
  markRead: (id, token, mid) =>
    request(`/api/mailboxes/${id}/messages/${mid}/read?token=${encodeURIComponent(token)}`, {
      method: 'PATCH',
    }),
  send: (id, token, payload) =>
    request(`/api/mailboxes/${id}/send?token=${encodeURIComponent(token)}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}

export function attachmentUrl(id, token, mid, index) {
  return `/api/mailboxes/${id}/messages/${mid}/attachments/${index}?token=${encodeURIComponent(token)}`
}
