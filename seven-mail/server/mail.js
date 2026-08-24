import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import nodemailer from 'nodemailer';
import { ATTACH_DIR, statements } from './db.js';
import { httpError } from './errors.js';

const domain = String(process.env.APP_DOMAIN || 'mail.example.com').toLowerCase().trim();
const provider = String(process.env.MAIL_PROVIDER || 'demo').toLowerCase().trim();
const ttlMs = (Number(process.env.MAILBOX_TTL_DAYS) || 7) * 24 * 60 * 60 * 1000;

const ALPHABET = 'abcdefghijkmnpqrstuvwxyz23456789';
const PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789-_';

function generatePassword(length = 14) {
  const bytes = crypto.randomBytes(length);
  let out = '';
  for (let i = 0; i < length; i += 1) {
    out += PASSWORD_ALPHABET[bytes[i] % PASSWORD_ALPHABET.length];
  }
  return out;
}

function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(password, salt, 64).toString('hex');
  return `${salt}:${hash}`;
}

function verifyPassword(password, stored) {
  if (!stored || !password) return false;
  const [salt, hash] = String(stored).split(':');
  if (!salt || !hash) return false;
  const actual = crypto.scryptSync(String(password), salt, 64);
  const expected = Buffer.from(hash, 'hex');
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}

const safeName = (name, index) => {
  const cleaned = String(name || `attachment-${index + 1}`)
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_')
    .slice(0, 80);
  return cleaned || `attachment-${index + 1}`;
};

function randomPart(length = 12) {
  const bytes = crypto.randomBytes(length);
  let out = '';
  for (let i = 0; i < length; i += 1) out += ALPHABET[bytes[i] % ALPHABET.length];
  return out;
}

export function appConfig() {
  return {
    domain,
    provider,
    ttlDays: Math.round(ttlMs / (24 * 60 * 60 * 1000)),
    adminRequired: Boolean(process.env.ADMIN_TOKEN),
  };
}

function publicMailbox(row, plainPassword) {
  if (!row) return null;
  const mailbox = {
    id: row.id,
    address: row.address,
    token: row.token,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
    lastActivityAt: row.last_activity_at,
  };
  if (plainPassword) mailbox.password = plainPassword;
  return mailbox;
}

export function createMailbox({ prefix = '' } = {}) {
  const local = String(prefix || '').trim().toLowerCase();
  let address;
  if (local) {
    if (!/^[a-z0-9][a-z0-9._-]{1,31}$/.test(local)) {
      throw httpError(400, '前缀只能包含字母、数字、点、下划线和短横线');
    }
    address = `${local}@${domain}`;
    if (statements.findMailboxByAddress.get(address)) {
      throw httpError(409, '这个邮箱地址已经被使用');
    }
  } else {
    for (let i = 0; i < 8; i += 1) {
      address = `${randomPart(10)}@${domain}`;
      if (!statements.findMailboxByAddress.get(address)) break;
    }
    if (!address || statements.findMailboxByAddress.get(address)) {
      throw httpError(500, '生成地址失败，请重试');
    }
  }

  const id = randomUUID();
  const token = randomPart(24);
  const password = generatePassword();
  const now = Date.now();
  statements.insertMailbox.run(id, address, token, hashPassword(password), now, now + ttlMs, now);
  return publicMailbox(statements.findMailboxById.get(id), password);
}

export function loginMailbox(address, password) {
  const row = statements.findMailboxByAddress.get(String(address || '').toLowerCase().trim());
  if (!row) throw httpError(404, '邮箱账号不存在');
  if (row.expires_at <= Date.now()) {
    deleteMailbox(row.id);
    throw httpError(410, '邮箱已过期并被销毁');
  }
  if (!verifyPassword(password, row.password_hash)) {
    throw httpError(401, '账号或密码不正确');
  }
  statements.touchMailbox.run(Date.now(), row.id);
  return publicMailbox(row);
}

export function authorizeMailbox(id, token) {
  const row = statements.findMailboxById.get(id);
  if (!row) throw httpError(404, '邮箱不存在');
  if (row.expires_at <= Date.now()) {
    deleteMailbox(row.id);
    throw httpError(410, '邮箱已过期并被销毁');
  }
  if (!token || token !== row.token) throw httpError(401, '访问令牌无效');
  statements.touchMailbox.run(Date.now(), row.id);
  return row;
}

export function findActiveMailboxByAddress(address) {
  const row = statements.findMailboxByAddress.get(String(address || '').toLowerCase().trim());
  if (!row || row.expires_at <= Date.now()) return null;
  statements.touchMailbox.run(Date.now(), row.id);
  return row;
}

export function deleteMailbox(id) {
  const rows = statements.listMessagesByMailbox.all(id);
  for (const row of rows) removeAttachmentFiles(row.attachments_json);
  statements.deleteMailbox.run(id);
}

export function cleanupExpired() {
  const expired = statements.listExpired.all(Date.now());
  for (const row of expired) deleteMailbox(row.id);
  return expired.length;
}

export function parseAddress(raw) {
  const s = String(raw || '').trim();
  const match = s.match(/[^\s<>,;]+@[^\s<>,;]+/i);
  const nameMatch = s.match(/^"?([^"<@]+)"?\s*</);
  return {
    address: match ? match[0].toLowerCase() : s.toLowerCase(),
    name: nameMatch ? nameMatch[1].trim() : s && !s.includes('@') ? s : '',
  };
}

export function splitAddresses(raw) {
  return String(raw || '')
    .split(/[,;]/)
    .map(parseAddress)
    .filter((item) => item.address);
}

export function attachmentMeta(attachmentsJson) {
  try {
    return JSON.parse(attachmentsJson || '[]');
  } catch {
    return [];
  }
}

export function removeAttachmentFiles(attachmentsJson) {
  for (const att of attachmentMeta(attachmentsJson)) {
    if (!att.file) continue;
    fs.rmSync(path.join(ATTACH_DIR, path.basename(att.file)), { force: true });
  }
}

function saveUploadAttachments(messageId, files = []) {
  const result = [];
  files.forEach((file, index) => {
    const filename = safeName(file.originalname, index);
    const storedName = `${messageId}-${index + 1}-${filename}`;
    fs.writeFileSync(path.join(ATTACH_DIR, storedName), file.buffer);
    result.push({
      filename,
      contentType: file.mimetype || 'application/octet-stream',
      size: file.size,
      file: storedName,
    });
  });
  return result;
}

function saveBase64Attachments(messageId, attachments = []) {
  const result = [];
  attachments.forEach((att, index) => {
    if (!att?.base64) return;
    const buffer = Buffer.from(att.base64, 'base64');
    if (!buffer.length) return;
    const filename = safeName(att.filename, index);
    const storedName = `${messageId}-${index + 1}-${filename}`;
    fs.writeFileSync(path.join(ATTACH_DIR, storedName), buffer);
    result.push({
      filename,
      contentType: att.contentType || 'application/octet-stream',
      size: buffer.length,
      file: storedName,
    });
  });
  return result;
}

function storeIncoming(mailbox, { sender, subject, text, html, attachments = [] }) {
  const parsed = parseAddress(sender);
  const messageId = `${Date.now()}.${randomPart(10)}@${domain}`;
  statements.insertMessage.run(
    mailbox.id,
    'incoming',
    null,
    parsed.address,
    parsed.name,
    mailbox.address,
    String(subject || ''),
    String(text || ''),
    String(html || ''),
    Date.now(),
    null,
    JSON.stringify(attachments),
  );
  return messageId;
}

function storeOutgoing(mailbox, { to, subject, text, html, attachments = [], messageId }) {
  const recipients = splitAddresses(to);
  const first = recipients[0] || {};
  statements.insertMessage.run(
    mailbox.id,
    'outgoing',
    messageId,
    first.address || to,
    first.name || '',
    mailbox.address,
    String(subject || ''),
    String(text || ''),
    String(html || ''),
    Date.now(),
    Date.now(),
    JSON.stringify(attachments),
  );
}

export async function sendMail(mailbox, payload) {
  const to = String(payload.to || '').trim();
  if (!to) throw httpError(400, '请填写收件人');
  const subject = String(payload.subject || '');
  const text = String(payload.text || '');
  const html = payload.html ? String(payload.html) : '';
  const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
  const messageId = `${Date.now()}.${randomPart(8)}@${domain}`;
  const from = mailbox.address;

  if (provider === 'demo') {
    const recipients = splitAddresses(to);
    let delivered = 0;
    for (const recipient of recipients) {
      const target = findActiveMailboxByAddress(recipient.address);
      if (!target) continue;
      const targetMessageId = `${Date.now()}.${randomPart(8)}@${domain}`;
      const atts = saveBase64Attachments(targetMessageId, attachments);
      storeIncoming(target, {
        sender: from,
        subject,
        text,
        html,
        attachments: atts,
      });
      delivered += 1;
    }
    if (!delivered) {
      throw httpError(400, '演示模式下只能发送给本站已生成的邮箱');
    }
    const atts = saveBase64Attachments(messageId, attachments);
    storeOutgoing(mailbox, { to, subject, text, html, attachments: atts, messageId });
    return { messageId };
  }

  if (provider === 'mailgun') {
    await sendViaMailgun({ from, to, subject, text, html, attachments });
    const atts = saveBase64Attachments(messageId, attachments);
    storeOutgoing(mailbox, { to, subject, text, html, attachments: atts, messageId });
    return { messageId };
  }

  if (provider === 'smtp') {
    await sendViaSmtp({ from, to, subject, text, html, attachments });
    const atts = saveBase64Attachments(messageId, attachments);
    storeOutgoing(mailbox, { to, subject, text, html, attachments: atts, messageId });
    return { messageId };
  }

  throw httpError(500, '邮件服务未正确配置');
}

async function sendViaMailgun({ from, to, subject, text, html, attachments }) {
  const apiKey = process.env.MAILGUN_API_KEY || '';
  if (!apiKey) throw httpError(500, '缺少 MAILGUN_API_KEY');
  const form = new FormData();
  form.append('from', from);
  form.append('to', to);
  form.append('subject', subject);
  form.append('text', text);
  if (html) form.append('html', html);
  for (const att of attachments) {
    if (!att.base64) continue;
    const buffer = Buffer.from(att.base64, 'base64');
    if (!buffer.length) continue;
    form.append(
      'attachment',
      new Blob([buffer], { type: att.contentType || 'application/octet-stream' }),
      att.filename || 'attachment',
    );
  }
  const response = await fetch(`https://api.mailgun.net/v3/${domain}/messages`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`,
    },
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw httpError(502, `邮件服务返回 ${response.status}${detail ? `: ${detail.slice(0, 300)}` : ''}`);
  }
}

async function sendViaSmtp({ from, to, subject, text, html, attachments }) {
  const host = process.env.SMTP_HOST || '';
  if (!host) throw httpError(500, '缺少 SMTP_HOST');
  const secure = process.env.SMTP_SECURE === 'ssl';
  const transport = nodemailer.createTransport({
    host,
    port: Number(process.env.SMTP_PORT) || (secure ? 465 : 587),
    secure,
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD || '' }
      : undefined,
    tls: { rejectUnauthorized: false },
    connectionTimeout: 30000,
    greetingTimeout: 30000,
  });
  try {
    await transport.sendMail({
      from,
      to,
      subject,
      text,
      html,
      attachments: attachments
        .filter((att) => att.base64)
        .map((att) => ({
          filename: att.filename || 'attachment',
          contentType: att.contentType || 'application/octet-stream',
          content: Buffer.from(att.base64, 'base64'),
        })),
    });
  } finally {
    transport.close();
  }
}

export function verifyMailgun(body) {
  const { timestamp, token, signature } = body || {};
  const key = process.env.MAILGUN_WEBHOOK_SIGNING_KEY || '';
  // 本地演示模式未配置签名密钥时暂不校验；正式部署必须配置 MAILGUN_WEBHOOK_SIGNING_KEY。
  if (!key) return true;
  if (!timestamp || !token || !signature) return false;
  const expected = crypto
    .createHmac('sha256', key)
    .update(`${timestamp}${token}`)
    .digest('hex');
  try {
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

export function handleInbound(body, files = []) {
  const data = body || {};
  const recipient = String(data.recipient || '').toLowerCase().trim();
  const mailbox = findActiveMailboxByAddress(recipient);
  if (!mailbox) return { ok: true, ignored: true };
  const messageId = `${Date.now()}.${randomPart(10)}@${domain}`;
  const attachments = saveUploadAttachments(messageId, files || []);
  storeIncoming(mailbox, {
    sender: data.sender || '',
    subject: data.subject || '',
    text: data['body-plain'] || data['stripped-text'] || '',
    html: data['body-html'] || data['stripped-html'] || '',
    attachments,
  });
  return { ok: true, ignored: false, messageId };
}
