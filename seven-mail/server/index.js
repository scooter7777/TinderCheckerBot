import 'dotenv/config';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import cors from 'cors';
import multer from 'multer';
import { ATTACH_DIR, statements } from './db.js';
import {
  appConfig,
  attachmentMeta,
  authorizeMailbox,
  cleanupExpired,
  createMailbox,
  deleteMailbox,
  handleInbound,
  loginMailbox,
  sendMail,
  verifyMailgun,
} from './mail.js';
import { httpError } from './errors.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST_DIR = path.join(__dirname, '..', 'dist');
const adminToken = String(process.env.ADMIN_TOKEN || '');
const app = express();
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 20 * 1024 * 1024 },
});

app.use(cors());
app.use(express.json({ limit: '25mb' }));
app.use(express.urlencoded({ extended: true }));

function mailboxParam(req) {
  const token = String(req.query.token || req.headers['x-mail-token'] || '');
  return authorizeMailbox(req.params.id, token);
}

function requireAdmin(req) {
  if (adminToken && req.get('x-admin-token') !== adminToken) {
    throw httpError(401, '需要管理员权限');
  }
}

app.get('/api/health', (req, res) => {
  res.json({ ok: true });
});

app.get('/api/config', (req, res) => {
  res.json(appConfig());
});

app.post('/api/mailboxes', (req, res) => {
  requireAdmin(req);
  const mailbox = createMailbox({ prefix: req.body?.prefix });
  res.status(201).json(mailbox);
});

app.post('/api/mailboxes/batch', (req, res) => {
  requireAdmin(req);
  const count = Math.min(100, Math.max(1, Number(req.body?.count) || 1));
  const prefix = String(req.body?.prefix || '');
  console.log(`[batch] count=${count} prefix=${prefix || '(random)'}`);
  const mailboxes = [];
  for (let i = 0; i < count; i += 1) {
    let itemPrefix = prefix;
    if (prefix && count > 1) {
      const suffix = String(i + 1);
      const keep = 32 - suffix.length - 1;
      itemPrefix = `${(prefix.length > keep ? prefix.slice(0, keep) : prefix)}-${suffix}`;
    }
    mailboxes.push(createMailbox({ prefix: itemPrefix }));
  }
  res.status(201).json({ mailboxes });
});

app.post('/api/admin/verify', (req, res) => {
  const token = String(req.body?.token || '');
  if (adminToken && token !== adminToken) throw httpError(401, '管理员密码错误');
  res.json({ ok: true });
});

app.post('/api/auth/login', (req, res) => {
  const { address, password } = req.body || {};
  if (!address || !password) throw httpError(400, '请输入账号和密码');
  res.json(loginMailbox(address, password));
});

app.get('/api/mailboxes/:id', (req, res) => {
  const mailbox = mailboxParam(req);
  const messages = statements.listMessages.all(mailbox.id);
  res.json({
    mailbox,
    unread: messages.filter((m) => !m.read_at).length,
    total: messages.length,
  });
});

app.delete('/api/mailboxes/:id', (req, res) => {
  mailboxParam(req);
  deleteMailbox(req.params.id);
  res.json({ ok: true });
});

app.get('/api/mailboxes/:id/messages', (req, res) => {
  const mailbox = mailboxParam(req);
  const rows = statements.listMessages.all(mailbox.id);
  const messages = rows.map((row) => ({
    id: row.id,
    direction: row.direction,
    fromAddress: row.from_address,
    fromName: row.from_name,
    toAddress: row.to_address,
    subject: row.subject || '(无主题)',
    snippet: String(row.text_body || '').replace(/\s+/g, ' ').slice(0, 140),
    receivedAt: row.received_at,
    read: Boolean(row.read_at),
    attachmentCount: attachmentMeta(row.attachments_json).length,
  }));
  res.json({ messages, unread: messages.filter((m) => !m.read).length });
});

app.get('/api/mailboxes/:id/messages/:mid', (req, res) => {
  const mailbox = mailboxParam(req);
  const row = statements.findMessage.get(Number(req.params.mid), mailbox.id);
  if (!row) throw httpError(404, '邮件不存在');
  if (!row.read_at) statements.markRead.run(Date.now(), row.id);
  const attachments = attachmentMeta(row.attachments_json).map((att, index) => ({
    ...att,
    index,
  }));
  res.json({
    id: row.id,
    direction: row.direction,
    messageId: row.message_id,
    fromAddress: row.from_address,
    fromName: row.from_name,
    toAddress: row.to_address,
    subject: row.subject,
    text: row.text_body,
    html: row.html_body,
    receivedAt: row.received_at,
    readAt: row.read_at,
    attachments,
  });
});

app.patch('/api/mailboxes/:id/messages/:mid/read', (req, res) => {
  const mailbox = mailboxParam(req);
  const row = statements.findMessage.get(Number(req.params.mid), mailbox.id);
  if (!row) throw httpError(404, '邮件不存在');
  statements.markRead.run(Date.now(), row.id);
  res.json({ ok: true });
});

app.post('/api/mailboxes/:id/send', async (req, res) => {
  const mailbox = mailboxParam(req);
  const result = await sendMail(mailbox, req.body || {});
  res.json(result);
});

app.get('/api/mailboxes/:id/messages/:mid/attachments/:index', (req, res) => {
  const mailbox = mailboxParam(req);
  const row = statements.findMessage.get(Number(req.params.mid), mailbox.id);
  if (!row) throw httpError(404, '邮件不存在');
  const att = attachmentMeta(row.attachments_json)[Number(req.params.index)];
  if (!att?.file) throw httpError(404, '附件不存在');
  const filePath = path.join(ATTACH_DIR, path.basename(att.file));
  if (!fs.existsSync(filePath)) throw httpError(404, '附件文件已丢失');
  res.setHeader('Content-Type', att.contentType || 'application/octet-stream');
  res.setHeader(
    'Content-Disposition',
    `attachment; filename*=UTF-8''${encodeURIComponent(att.filename)}`,
  );
  res.sendFile(filePath);
});

app.post('/api/inbound/mailgun', upload.any(), (req, res) => {
  if (!verifyMailgun(req.body)) throw httpError(401, 'Webhook 签名无效');
  res.json(handleInbound(req.body || {}, req.files || []));
});

const cleanup = () => {
  try {
    const removed = cleanupExpired();
    if (removed) console.log(`[cleanup] 已销毁 ${removed} 个过期邮箱`);
  } catch (error) {
    console.error('[cleanup]', error);
  }
};
cleanup();
setInterval(cleanup, 10 * 60 * 1000);

app.use('/api', (req, res) => {
  res.status(404).json({ error: '接口不存在' });
});

if (fs.existsSync(DIST_DIR)) {
  app.use(express.static(DIST_DIR, {
    setHeaders(res, filePath) {
      if (filePath.endsWith('.html')) {
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
      }
    },
  }));
  app.use((req, res, next) => {
    if (req.method === 'GET' && !req.path.startsWith('/api/')) {
      return res.sendFile(path.join(DIST_DIR, 'index.html'));
    }
    next();
  });
}

app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ error: `上传失败: ${err.message}` });
  }
  const status = err.status || 500;
  if (status >= 500) console.error(err);
  res.status(status).json({ error: err.message || '服务器内部错误' });
});

const PORT = Number(process.env.APP_PORT) || 3002;
app.listen(PORT, () => {
  console.log(`Seven Mail API listening on http://localhost:${PORT}`);
  console.log(`Domain: ${appConfig().domain}  Provider: ${appConfig().provider}`);
});
