-- Rastreio Facil — esquema do banco D1 (Cloudflare). Espelha o SQLite criado por db.py (init_db).
-- Aplicar: npx wrangler d1 execute rastreio-facil --remote --file cloudflare/schema.sql
CREATE TABLE IF NOT EXISTS envios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  destinatario TEXT DEFAULT '', codigo TEXT NOT NULL,
  celular TEXT DEFAULT '', email TEXT DEFAULT '',
  descricao TEXT DEFAULT '', status TEXT DEFAULT 'pendente',
  notificado INTEGER DEFAULT 0,
  criado_em TEXT DEFAULT (datetime('now')),
  atualizado_em TEXT DEFAULT (datetime('now')),
  criado_por INTEGER DEFAULT NULL,
  excluido_por INTEGER DEFAULT NULL,
  excluido_em TEXT DEFAULT NULL,
  status_anterior TEXT DEFAULT NULL);
CREATE INDEX IF NOT EXISTS idx_envios_codigo ON envios(codigo);
CREATE INDEX IF NOT EXISTS idx_envios_status ON envios(status);

CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL DEFAULT '', email TEXT UNIQUE NOT NULL,
  senha_hash TEXT NOT NULL, admin INTEGER DEFAULT 0,
  ativo INTEGER DEFAULT 1,
  criado_em TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS sessoes (
  token TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL,
  expira_em TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  envio_id INTEGER NOT NULL, de_status TEXT DEFAULT '',
  para_status TEXT DEFAULT '', por_usuario INTEGER DEFAULT NULL,
  detalhe TEXT DEFAULT '',
  criado_em TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_eventos_envio ON eventos(envio_id);

-- cache do rastreio automatico (1 linha por envio; eventos = JSON em texto)
CREATE TABLE IF NOT EXISTS rastreios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  envio_id INTEGER UNIQUE NOT NULL, situacao TEXT DEFAULT '',
  carrier TEXT DEFAULT '', eventos TEXT DEFAULT '[]',
  consultado_em TEXT DEFAULT '');

-- anti brute-force do login (no Worker nao ha memoria compartilhada entre requisicoes)
CREATE TABLE IF NOT EXISTS login_falhas (ip TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_login_falhas_ip ON login_falhas(ip, ts);
