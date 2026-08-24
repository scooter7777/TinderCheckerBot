import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.join(__dirname, '..', 'data');
export const ATTACH_DIR = path.join(DATA_DIR, 'attachments');

fs.mkdirSync(DATA_DIR, { recursive: true });
fs.mkdirSync(ATTACH_DIR, { recursive: true });

export const db = new Database(path.join(DATA_DIR, 'seven-mail.db'));
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS mailboxes (
    id TEXT PRIMARY KEY,
    address TEXT UNIQUE NOT NULL,
    token TEXT NOT NULL,
    password_hash TEXT,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    last_activity_at INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mailbox_id TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'incoming',
    message_id TEXT,
    from_address TEXT,
    from_name TEXT,
    to_address TEXT,
    subject TEXT DEFAULT '',
    text_body TEXT,
    html_body TEXT,
    received_at INTEGER NOT NULL,
    read_at INTEGER,
    attachments_json TEXT DEFAULT '[]',
    FOREIGN KEY (mailbox_id) REFERENCES mailboxes(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_mailboxes_address ON mailboxes(address);
  CREATE INDEX IF NOT EXISTS idx_mailboxes_expires ON mailboxes(expires_at);
  CREATE INDEX IF NOT EXISTS idx_messages_mailbox ON messages(mailbox_id, received_at DESC);
`);

const mailboxColumns = db.prepare('PRAGMA table_info(mailboxes)').all().map((c) => c.name);
if (!mailboxColumns.includes('password_hash')) {
  db.exec('ALTER TABLE mailboxes ADD COLUMN password_hash TEXT');
}

export const statements = {
  insertMailbox: db.prepare(
    `INSERT INTO mailboxes (id, address, token, password_hash, created_at, expires_at, last_activity_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ),
  findMailboxById: db.prepare('SELECT * FROM mailboxes WHERE id = ?'),
  findMailboxByAddress: db.prepare('SELECT * FROM mailboxes WHERE address = ?'),
  touchMailbox: db.prepare('UPDATE mailboxes SET last_activity_at = ? WHERE id = ?'),
  deleteMailbox: db.prepare('DELETE FROM mailboxes WHERE id = ?'),
  listExpired: db.prepare('SELECT * FROM mailboxes WHERE expires_at <= ?'),
  insertMessage: db.prepare(`
    INSERT INTO messages (
      mailbox_id, direction, message_id, from_address, from_name, to_address,
      subject, text_body, html_body, received_at, read_at, attachments_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `),
  listMessagesByMailbox: db.prepare(
    'SELECT * FROM messages WHERE mailbox_id = ? ORDER BY received_at DESC',
  ),
  listMessages: db.prepare(`
    SELECT id, direction, message_id, from_address, from_name, to_address,
      subject, text_body, html_body, received_at, read_at, attachments_json
    FROM messages WHERE mailbox_id = ? ORDER BY received_at DESC
  `),
  findMessage: db.prepare('SELECT * FROM messages WHERE id = ? AND mailbox_id = ?'),
  markRead: db.prepare('UPDATE messages SET read_at = COALESCE(read_at, ?) WHERE id = ?'),
};
