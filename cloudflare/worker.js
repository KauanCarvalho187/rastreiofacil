/* Rastreio Facil — backend para Cloudflare Workers + D1.
   Porte 1:1 das rotas do main.py (FastAPI): mesmas URLs, mesmos corpos e os mesmos erros
   ({"detail": "..."}), para o static/app.js funcionar igual nos dois ambientes.
   Mudou uma regra no main.py / rastreio.py? Mude aqui tambem. */
import { connect } from 'cloudflare:sockets';

const APP_VERSAO = '27';
const RASTREIO_URL_PADRAO = 'https://api-labs.wonca.com.br/wonca.labs.v1.LabsService/Track';
const REGEX_CODIGO = /^[A-Za-z]{2}\d{9}BR$/;
const REGEX_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const STATUS_ATIVOS = ['pendente', 'a_caminho', 'entregue'];
const E_PACK = '\u{1F4E6}', E_WAVE = '\u{1F44B}', E_LIST = '\u{1F4CB}', E_LINK = '\u{1F517}', SETA = '▸';

class Http extends Error {
  constructor(status, detail){ super(detail); this.status = status; this.detail = detail; }
}
const json = (dados, status = 200, headers = {}) =>
  new Response(JSON.stringify(dados), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers } });

/* ---------- banco (D1) ---------- */
const fetchAll = async (env, sql, args = []) => (await env.DB.prepare(sql).bind(...args).all()).results || [];
const fetchOne = (env, sql, args = []) => env.DB.prepare(sql).bind(...args).first();
async function execute(env, sql, args = []){
  const r = await env.DB.prepare(sql).bind(...args).run();
  return [r.meta.changes || 0, r.meta.last_row_id];
}

/* ---------- utilitarios ---------- */
const iso = d => d.toISOString().slice(0, 19).replace('T', ' ');
const agoraIso = () => iso(new Date());
const num = (v, padrao) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : padrao; };
const linkRastreio = codigo => `https://rastreamento.correios.com.br/app/index.php?objeto=${codigo}`;
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const deHex = s => new Uint8Array((s.match(/../g) || []).map(h => parseInt(h, 16)));
const escHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[c]));
const b64utf8 = s => { let bin = ''; for (const b of new TextEncoder().encode(s)) bin += String.fromCharCode(b); return btoa(bin); };

function validarCodigo(codigo){
  const c = String(codigo || '').trim().toUpperCase();
  if (!REGEX_CODIGO.test(c)) throw new Http(422, `código inválido '${c}' — use 2 letras + 9 números + BR`);
  return c;
}
function validarEmail(email){
  email = String(email || '').trim();
  if (!email) return email;
  if (email.includes(' ')) throw new Http(422, `E-mail invalido: ${email} — nao pode ter espacos`);
  if (!email.includes('@')) throw new Http(422, `E-mail invalido: ${email} — falta o @ (ex: nome@dominio.com)`);
  const i = email.indexOf('@'), local = email.slice(0, i), dom = email.slice(i + 1);
  if (!local) throw new Http(422, `E-mail invalido: ${email} — falta o nome antes do @ (ex: nome@dominio.com)`);
  if (!dom) throw new Http(422, `E-mail invalido: ${email} — falta o dominio depois do @ (ex: nome@dominio.com)`);
  if (!dom.includes('.')) throw new Http(422, `E-mail invalido: ${email} — falta o ponto no dominio (ex: dominio.com)`);
  if (!REGEX_EMAIL.test(email)) throw new Http(422, `E-mail invalido: ${email} — formato esperado: nome@dominio.com`);
  return email;
}
function normalizarCelular(valor){
  let d = String(valor || '').replace(/\D/g, '');
  if (d.startsWith('0055')) d = '55' + d.slice(4);
  if (d.startsWith('0') && d.length > 1) d = d.slice(1);
  if (d.startsWith('55') && (d.length === 12 || d.length === 13)) d = d.slice(2);
  if (d && d.length !== 10 && d.length !== 11) throw new Http(422, 'Celular invalido — use DDD + 8/9 digitos, ex: (11) 98765-4321');
  return d;
}

/* ---------- senha: PBKDF2-SHA256, 100k iteracoes, "sal$hash" (mesmo formato do main.py) ---------- */
async function pbkdf2(senha, salHex){
  const chave = await crypto.subtle.importKey('raw', new TextEncoder().encode(senha), 'PBKDF2', false, ['deriveBits']);
  return hex(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: deHex(salHex), iterations: 100000 }, chave, 256));
}
async function hashSenha(senha){
  const sal = hex(crypto.getRandomValues(new Uint8Array(16)));
  return `${sal}$${await pbkdf2(senha, sal)}`;
}
async function verificarSenha(senha, armazenada){
  const [sal, h] = String(armazenada || '').split('$');
  if (!sal || !h || !/^[0-9a-f]+$/i.test(sal)) return false;
  const calc = await pbkdf2(String(senha), sal);
  if (calc.length !== h.length) return false;
  let dif = 0;
  for (let i = 0; i < calc.length; i++) dif |= calc.charCodeAt(i) ^ h.charCodeAt(i);
  return dif === 0;
}

/* ---------- autenticacao ---------- */
const contarUsuarios = async env => Number((await fetchOne(env, 'SELECT COUNT(*) AS n FROM usuarios'))?.n || 0);
function bearer(req){
  const a = req.headers.get('Authorization') || '';
  return a.startsWith('Bearer ') ? a.slice(7).trim() : '';
}
async function authUsuario(env, req){
  const token = bearer(req);
  if (!token) throw new Http(401, 'Nao autenticado');
  const row = await fetchOne(env,
    'SELECT u.id, u.nome, u.email, u.admin FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id '
    + 'WHERE s.token = ? AND s.expira_em > ? AND u.ativo = 1', [token, agoraIso()]);
  if (!row) throw new Http(401, 'Sessao invalida ou expirada');
  return row;
}
async function authOpcional(env, req){
  if (await contarUsuarios(env) === 0) return { id: 0, nome: 'setup', email: '', admin: true, bootstrap: true };
  return authUsuario(env, req);
}
async function corpo(req){
  try { const d = await req.json(); return (d && typeof d === 'object') ? d : {}; }
  catch (e) { return {}; }
}

function rowToEnvio(row){
  return {
    _id: row.id,
    destinatario: row.destinatario || '',
    codigo: row.codigo,
    celular: row.celular || '',
    email: row.email || '',
    descricao: row.descricao || '',
    status: row.status || 'pendente',
    notificado: !!row.notificado,
    criado_em: row.criado_em != null ? String(row.criado_em) : '',
    link: linkRastreio(row.codigo || ''),
    excluido_por: row.excluido_por ?? null,
    excluido_em: row.excluido_em ?? null,
    status_anterior: row.status_anterior ?? null,
    criado_por_nome: row.criado_por_nome ?? null,
    excluido_por_nome: row.excluido_por_nome ?? null,
  };
}
async function registrarEvento(env, envioId, de, para, porUsuario, detalhe = ''){
  try {
    await execute(env, 'INSERT INTO eventos (envio_id,de_status,para_status,por_usuario,detalhe) VALUES (?,?,?,?,?)',
      [envioId, de || '', para || '', porUsuario ?? null, detalhe || '']);
  } catch (e) { /* historico nunca derruba a operacao principal */ }
}

/* ---------- e-mail (SMTP direto via socket TCP; sem credenciais -> o front cai no mailto:) ---------- */
const smtpConfigurado = env => !!(env.SMTP_USER && env.SMTP_PASS);
function dataEnvioBr(criadoEm){
  const m = String(criadoEm || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  return new Date().toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
}
function montarHtmlEmail(env, destinatario, codigo, descricao = '', dataEnvio = ''){
  const nome = escHtml(String(destinatario || '').trim() || 'cliente');
  const cod = escHtml(codigo || ''), link = linkRastreio(String(codigo || ''));
  const detalhes = [`${SETA} <b>Código:</b> ${cod}`];
  if (String(descricao || '').trim()) detalhes.push(`${SETA} <b>Descrição:</b> ${escHtml(String(descricao).trim())}`);
  detalhes.push(`${SETA} <b>Data de Envio:</b> ${escHtml(dataEnvio || dataEnvioBr(null))}`);
  return `
<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#222;line-height:1.6">
  <div style="background:#0f172a;color:#fff;padding:18px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:18px">${E_PACK} Correios — Código de Rastreio</h2>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:0;padding:24px;border-radius:0 0 10px 10px">
    <p style="margin:0 0 12px">Olá, <b>${nome}</b>! Tudo bem? ${E_WAVE}</p>
    <p style="margin:0 0 16px">Sua correspondência foi postada e já está em rota de entrega.</p>
    <p style="margin:0 0 6px"><b>${E_LIST} Detalhes do envio:</b><br>${detalhes.join('<br>')}</p>
    <p style="margin:20px 0">
      <a href="${link}" style="background:#2563eb;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;display:inline-block">${E_LINK} Acompanhar em tempo real</a>
    </p>
    <p style="font-size:12px;color:#64748b;word-break:break-all;margin:0 0 16px">Ou copie o link:<br>${link}</p>
    <p style="margin:0 0 8px">Qualquer dúvida, estamos à disposição!</p>
    <p style="margin:0">Atenciosamente,<br><b>${escHtml(env.SENDER_NAME || 'Rastreio Facil')}</b></p>
  </div>
</div>`;
}
async function smtpEnviar(env, destino, assunto, html){
  const host = env.SMTP_HOST || 'smtp.gmail.com', porta = num(env.SMTP_PORT, 587);
  const tlsDireto = porta === 465;
  let sock = connect({ hostname: host, port: porta }, { secureTransport: tlsDireto ? 'on' : 'starttls' });
  let leitor = sock.readable.getReader(), escritor = sock.writable.getWriter();
  const enc = new TextEncoder(), dec = new TextDecoder();
  let buf = '';
  /* resposta SMTP pode ter varias linhas: "250-..." continua, "250 ..." encerra */
  const ler = async () => {
    for (;;) {
      const linhas = buf.split('\r\n');
      for (let i = 0; i < linhas.length - 1; i++) {
        if (/^\d{3} /.test(linhas[i])) { buf = linhas.slice(i + 1).join('\r\n'); return linhas[i]; }
      }
      const { value, done } = await leitor.read();
      if (done) throw new Error('conexao SMTP fechada');
      buf += dec.decode(value, { stream: true });
    }
  };
  const cmd = async (linha, esperado) => {
    if (linha !== null) await escritor.write(enc.encode(linha + '\r\n'));
    const r = await ler();
    if (!r.startsWith(esperado)) throw new Error('SMTP respondeu: ' + r.slice(0, 120));
  };
  try {
    await cmd(null, '220');
    await cmd('EHLO rastreio-facil', '250');
    if (!tlsDireto) {
      await cmd('STARTTLS', '220');
      leitor.releaseLock(); escritor.releaseLock();
      sock = sock.startTls();
      leitor = sock.readable.getReader(); escritor = sock.writable.getWriter(); buf = '';
      await cmd('EHLO rastreio-facil', '250');
    }
    await cmd('AUTH LOGIN', '334');
    await cmd(b64utf8(env.SMTP_USER), '334');
    await cmd(b64utf8(env.SMTP_PASS), '235');
    await cmd(`MAIL FROM:<${env.SMTP_USER}>`, '250');
    await cmd(`RCPT TO:<${destino}>`, '25');
    await cmd('DATA', '354');
    const mime = s => `=?UTF-8?B?${b64utf8(s)}?=`;
    /* corpo em base64 (linhas de 76): sem risco de linha comecando com "." nem de acento quebrado */
    const msg = [
      `From: ${mime(env.SENDER_NAME || 'Rastreio Facil')} <${env.SMTP_USER}>`,
      `To: ${destino}`,
      `Subject: ${mime(assunto)}`,
      `Date: ${new Date().toUTCString().replace('GMT', '+0000')}`,
      `Message-ID: <${crypto.randomUUID()}@rastreio-facil>`,
      'MIME-Version: 1.0',
      'Content-Type: text/html; charset=utf-8',
      'Content-Transfer-Encoding: base64',
      '',
      ...(b64utf8(html).match(/.{1,76}/g) || []),
    ].join('\r\n');
    await cmd(msg + '\r\n.', '250');
    await cmd('QUIT', '221').catch(() => {});
  } finally {
    try { await sock.close(); } catch (e) { /* ja fechado */ }
  }
}
async function enviarEmail(env, destino, assunto, html){
  if (!smtpConfigurado(env) || !REGEX_EMAIL.test(destino)) return false;
  try {
    await Promise.race([
      smtpEnviar(env, destino, assunto, html),
      new Promise((_, rej) => setTimeout(() => rej(new Error('tempo esgotado')), 20000)),
    ]);
    return true;
  } catch (e) {
    console.log('[SMTP] falha:', e.message);
    return false;
  }
}

/* ---------- rastreio automatico (mesma normalizacao do rastreio.py) ---------- */
const rastreioConfigurado = env => !!String(env.RASTREIO_API_KEY || '').trim();
const dataEvento = v => String((v && typeof v === 'object' ? v.date : v) || '').replace('T', ' ').slice(0, 16);
function unidade(u){
  if (!u || typeof u !== 'object') return '';
  const end = u.endereco || {};
  const cidade = [String(end.cidade || '').trim(), String(end.uf || '').trim()].filter(Boolean).join('/');
  return [String(u.nome || u.tipo || '').trim(), cidade].filter(Boolean).join(' — ');
}
export function normalizarRastreio(resp){
  resp = (resp && typeof resp === 'object') ? resp : {};
  let dados = {};
  try { dados = typeof resp.json === 'string' ? JSON.parse(resp.json) : (resp.json || resp); } catch (e) { dados = {}; }
  if (!dados || typeof dados !== 'object' || Array.isArray(dados)) dados = {};
  if (Array.isArray(dados.objetos) && dados.objetos.length) dados = dados.objetos[0] || {};
  let eventos = [], entregue = false;
  for (const ev of Array.isArray(dados.eventos) ? dados.eventos : []) {
    if (!ev || typeof ev !== 'object') continue;
    eventos.push({
      data: dataEvento(ev.dtHrCriado),
      descricao: String(ev.descricao || '').trim(),
      detalhe: String(ev.detalhe || '').trim(),
      local: unidade(ev.unidade),
      destino: unidade(ev.unidadeDestino),
    });
  }
  for (const mod of Array.isArray(dados.module) ? dados.module : []) {
    if (!mod || typeof mod !== 'object') continue;
    if (['DELIVERED', 'SIGNIN'].includes(String(mod.status || '').toUpperCase())) entregue = true;
    for (const ev of Array.isArray(mod.detailList) ? mod.detailList : []) {
      if (!ev || typeof ev !== 'object') continue;
      eventos.push({
        data: dataEvento(ev.timeStr),
        descricao: String(ev.standerdDesc || ev.desc || '').trim(),
        detalhe: '',
        local: (ev.group && typeof ev.group === 'object') ? String(ev.group.nodeDesc || '').trim() : '',
        destino: '',
      });
    }
  }
  eventos = eventos.filter(e => e.descricao);
  eventos.sort((a, b) => (a.data < b.data ? 1 : a.data > b.data ? -1 : 0));
  /* "Objeto entregue ao destinatario/remetente"; nao confundir com "saiu para entrega" ou "nao entregue" */
  if (eventos.length && eventos[0].descricao.toLowerCase().startsWith('objeto entregue')) entregue = true;
  return {
    carrier: String(resp.carrier || ''),
    situacao: entregue ? 'entregue' : (eventos.length ? 'em_transito' : 'sem_eventos'),
    eventos,
    mensagem: String(dados.mensagem || '').trim(),
  };
}
async function consultarRastreio(env, codigo){
  if (!rastreioConfigurado(env)) throw new Http(503, 'Rastreio automatico nao configurado (defina RASTREIO_API_KEY)');
  let r;
  try {
    r = await fetch(env.RASTREIO_API_URL || RASTREIO_URL_PADRAO, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Apikey ${String(env.RASTREIO_API_KEY).trim()}` },
      body: JSON.stringify({ code: codigo }),
      signal: AbortSignal.timeout(25000),
    });
  } catch (e) {
    throw new Http(502, 'Servico de rastreio nao respondeu — tente de novo em instantes');
  }
  if (r.status === 401) throw new Http(502, 'Chave da API de rastreio invalida (RASTREIO_API_KEY)');
  if (r.status === 429) throw new Http(502, 'Limite de consultas da API de rastreio atingido');
  if (r.status !== 200) throw new Http(502, `Rastreio indisponivel no momento (provedor respondeu ${r.status}) — tente de novo em instantes`);
  let dados = {};
  try { dados = await r.json(); } catch (e) { /* corpo invalido = sem eventos */ }
  return normalizarRastreio(dados);
}
function cacheValido(env, cache){
  if (cache.situacao === 'entregue') return true;  /* entregue nao muda mais: nao gasta cota */
  const quando = Date.parse(String(cache.consultado_em || '').replace(' ', 'T') + 'Z');
  if (!Number.isFinite(quando)) return false;
  return Date.now() - quando < num(env.RASTREIO_CACHE_MIN, 30) * 60000;
}
function rastreioResposta(row, cache, emCache, aviso = '', statusAtualizado = false){
  let eventos = [];
  try { eventos = JSON.parse(cache.eventos || '[]'); } catch (e) { eventos = []; }
  return {
    codigo: row.codigo, status: row.status,
    situacao: cache.situacao || 'sem_eventos',
    carrier: cache.carrier || '', eventos,
    consultado_em: cache.consultado_em || '',
    cache: emCache, aviso, status_atualizado: statusAtualizado,
    link: linkRastreio(row.codigo),
  };
}

/* ---------- rotas ---------- */
const rotas = [];
const rota = (metodo, caminho, fn) => rotas.push({
  metodo, fn,
  rx: new RegExp('^' + caminho.replace(/:id/g, '(\\d+)') + '/?$'),
});

async function statusBanco(env){
  const st = { configured: true, connected: true, driver: 'd1', url_safe: '' };
  try { await fetchOne(env, 'SELECT 1 AS ok'); }
  catch (e) { st.connected = false; st.error = String(e.message || e).slice(0, 300); }
  return st;
}
rota('GET', '/api/health', async (env) => {
  const st = await statusBanco(env);
  return { ok: st.connected, db: st, smtp: smtpConfigurado(env), rastreio: rastreioConfigurado(env) };
});
rota('GET', '/api/db-status', async (env) => statusBanco(env));
rota('GET', '/api/versao', async () => ({ versao: APP_VERSAO }));

rota('GET', '/api/auth/estado', async (env, req) => {
  const tem = await contarUsuarios(env) > 0;
  let admin = false;
  if (tem && bearer(req)) {
    try { admin = !!(await authUsuario(env, req)).admin; } catch (e) { admin = false; }
  }
  return { temUsuarios: tem, admin };
});

rota('POST', '/api/envios', async (env, req) => {
  const usuario = await authOpcional(env, req);
  const payload = await corpo(req);
  const m = 'envios' in payload ? payload.envios : null;
  const itens = m == null ? [payload] : (Array.isArray(m) ? m : [m]);
  if (!itens.length) throw new Http(422, 'Corpo vazio ou invalido');
  if (itens.length > 500) throw new Http(422, 'Lote muito grande (máximo 500 por vez)');
  const norm = [], erros = [], vistos = new Set();
  itens.forEach((it, idx) => {
    const lin = idx + 1;
    if (!it || typeof it !== 'object' || Array.isArray(it)) { erros.push(`linha ${lin}: item inválido`); return; }
    const nome = String(it.destinatario || it.nome || '').trim();
    const codRaw = String(it.codigo ?? ''), mailRaw = String(it.email ?? ''), celRaw = String(it.celular ?? '');
    const desc = String(it.descricao || it.observacoes || '').trim();
    let status = String(it.status || 'pendente').trim().toLowerCase();
    if (!STATUS_ATIVOS.includes(status)) status = 'pendente';
    if (!nome) { erros.push(`linha ${lin}: destinatário vazio`); return; }
    let codigo, email, celular;
    try { codigo = validarCodigo(codRaw); }
    catch (e) { erros.push(`linha ${lin} (${codRaw.trim() || 'vazio'}): código inválido — use 2 letras + 9 números + BR`); return; }
    try { email = validarEmail(mailRaw); }
    catch (e) { erros.push(`linha ${lin}: e-mail inválido (${mailRaw.trim()})`); return; }
    try { celular = normalizarCelular(celRaw); }
    catch (e) { erros.push(`linha ${lin}: celular inválido (${celRaw.trim()}) — use DDD + 8/9 dígitos`); return; }
    if (!email && !celular) { erros.push(`linha ${lin}: Informe ao menos e-mail ou WhatsApp`); return; }
    if (vistos.has(codigo)) { erros.push(`linha ${lin}: código duplicado na planilha (${codigo})`); return; }
    vistos.add(codigo);
    norm.push([nome, codigo, celular, email, desc, status]);
  });
  if (erros.length && !norm.length) throw new Http(422, 'Nenhuma linha válida. ' + erros.slice(0, 8).join('; '));
  const criados = [], uid = usuario.id || null;
  for (const [nome, codigo, celular, email, desc, status] of norm) {
    if (await fetchOne(env, 'SELECT id FROM envios WHERE codigo = ?', [codigo])) { erros.push(`${codigo}: já cadastrado (ignorado)`); continue; }
    const [, ultimo] = await execute(env,
      'INSERT INTO envios (destinatario,codigo,celular,email,descricao,status,criado_por) VALUES (?,?,?,?,?,?,?)',
      [nome, codigo, celular, email, desc, status, uid]);
    criados.push(rowToEnvio(await fetchOne(env, 'SELECT * FROM envios WHERE id = ?', [ultimo])));
  }
  let msg = `${criados.length} envio(s) criado(s)`;
  if (erros.length) msg += ` — ${erros.length} ignorado(s): ` + erros.slice(0, 8).join('; ');
  return { message: msg, envios: criados, erros };
});

rota('GET', '/api/envios', async (env, req, _id, url) => {
  const usuario = await authOpcional(env, req);
  const q = url.searchParams.get('q') || '', status = url.searchParams.get('status') || '';
  const page = num(url.searchParams.get('page') ?? '1', NaN), limit = num(url.searchParams.get('limit') ?? '200', NaN);
  if (!(page >= 1) || !(limit >= 1 && limit <= 500)) throw new Http(422, 'page/limit invalidos');
  const where = [], args = [];
  if (status && [...STATUS_ATIVOS, 'excluido'].includes(status)) { where.push('e.status = ?'); args.push(status); }
  else if (!status) { where.push('e.status IN (?,?,?)'); args.push(...STATUS_ATIVOS); }
  if (q) {
    const like = `%${q.trim()}%`;
    where.push('(e.destinatario LIKE ? OR e.codigo LIKE ? OR e.descricao LIKE ?)');
    args.push(like, like, like);
  }
  const w = where.length ? 'WHERE ' + where.join(' AND ') : '';
  const total = Number((await fetchOne(env, `SELECT COUNT(*) AS n FROM envios e ${w}`, args))?.n || 0);
  /* quem excluiu so aparece para admin */
  const admin = !!usuario.admin;
  const rows = await fetchAll(env, `
    SELECT e.*, u_cri.nome AS criado_por_nome, ${admin ? 'u_del.nome' : 'NULL'} AS excluido_por_nome
    FROM envios e
    LEFT JOIN usuarios u_cri ON u_cri.id = e.criado_por
    ${admin ? 'LEFT JOIN usuarios u_del ON u_del.id = e.excluido_por' : ''}
    ${w}
    ORDER BY e.id DESC LIMIT ? OFFSET ?`, [...args, limit, (page - 1) * limit]);
  return { envios: rows.map(rowToEnvio), total, page, limit };
});

rota('PUT', '/api/envios/:id', async (env, req, id) => {
  const usuario = await authOpcional(env, req);
  const row = await fetchOne(env, 'SELECT * FROM envios WHERE id = ?', [id]);
  if (!row) throw new Http(404, 'Envio nao encontrado');
  const upd = await corpo(req);
  const novos = [
    upd.destinatario != null ? String(upd.destinatario).trim() : row.destinatario,
    upd.codigo ? validarCodigo(upd.codigo) : row.codigo,
    upd.celular != null ? normalizarCelular(upd.celular) : row.celular,
    upd.email != null ? validarEmail(upd.email) : row.email,
    upd.descricao != null ? String(upd.descricao).trim() : row.descricao,
  ];
  if (!String(novos[0] || '').trim()) throw new Http(422, 'Destinatario vazio');
  if (!novos[3] && !novos[2]) throw new Http(422, 'Informe ao menos e-mail ou WhatsApp');
  if (await fetchOne(env, 'SELECT id FROM envios WHERE codigo = ? AND id <> ?', [novos[1], id]))
    throw new Http(409, `Codigo ${novos[1]} ja usado em outro envio`);
  await execute(env, 'UPDATE envios SET destinatario=?, codigo=?, celular=?, email=?, descricao=?, atualizado_em=? WHERE id=?',
    [...novos, agoraIso(), id]);
  if (upd.status) {
    const s = String(upd.status).toLowerCase();
    if (STATUS_ATIVOS.includes(s)) {
      await execute(env, 'UPDATE envios SET status=?, notificado=?, atualizado_em=? WHERE id=?', [s, s !== 'pendente' ? 1 : 0, agoraIso(), id]);
      await registrarEvento(env, id, row.status, s, usuario.id, 'edicao');
    }
  }
  return rowToEnvio(await fetchOne(env, 'SELECT * FROM envios WHERE id = ?', [id]));
});

rota('PATCH', '/api/envios/:id/status', async (env, req, id) => {
  const usuario = await authOpcional(env, req);
  const s = String((await corpo(req)).status || '').toLowerCase();
  if (!STATUS_ATIVOS.includes(s)) throw new Http(422, 'status deve ser pendente, a_caminho ou entregue');
  const anterior = await fetchOne(env, 'SELECT status FROM envios WHERE id = ?', [id]);
  const [n] = await execute(env, 'UPDATE envios SET status=?, notificado=?, atualizado_em=? WHERE id=?', [s, s !== 'pendente' ? 1 : 0, agoraIso(), id]);
  if (n === 0) throw new Http(404, 'Envio nao encontrado');
  await registrarEvento(env, id, anterior?.status || '', s, usuario.id, 'status');
  return rowToEnvio(await fetchOne(env, 'SELECT * FROM envios WHERE id = ?', [id]));
});

rota('PATCH', '/api/envios/:id/notificado', async (env, req, id) => {
  const usuario = await authOpcional(env, req);
  const anterior = await fetchOne(env, 'SELECT status FROM envios WHERE id = ?', [id]);
  if (!anterior) throw new Http(404, 'Envio nao encontrado');
  /* nao regride status: so "pendente" avanca para "a_caminho" ao notificar */
  const s = (anterior.status || 'pendente') === 'pendente' ? 'a_caminho' : anterior.status;
  await execute(env, 'UPDATE envios SET status=?, notificado=1, atualizado_em=? WHERE id=?', [s, agoraIso(), id]);
  await registrarEvento(env, id, anterior.status || '', s, usuario.id, 'notificado');
  return { message: 'Marcado como notificado' };
});

rota('DELETE', '/api/envios/:id', async (env, req, id) => {
  /* soft delete: vai para a lixeira guardando quem excluiu e o status anterior */
  const usuario = await authOpcional(env, req);
  const row = await fetchOne(env, 'SELECT id, status FROM envios WHERE id=?', [id]);
  if (!row) throw new Http(404, 'Envio nao encontrado');
  await execute(env, "UPDATE envios SET status='excluido', excluido_por=?, excluido_em=?, status_anterior=? WHERE id=?",
    [usuario.id, agoraIso(), row.status, id]);
  await registrarEvento(env, id, row.status, 'excluido', usuario.id, 'Movido para lixeira');
  return { message: 'Envio movido para lixeira' };
});

rota('POST', '/api/envios/:id/restaurar', async (env, req, id) => {
  const usuario = await authUsuario(env, req);
  if (!usuario.admin) throw new Http(403, 'Apenas administradores podem restaurar da lixeira');
  const row = await fetchOne(env, "SELECT id, status_anterior FROM envios WHERE id=? AND status='excluido'", [id]);
  if (!row) throw new Http(404, 'Envio nao encontrado na lixeira');
  const voltar = row.status_anterior || 'pendente';
  await execute(env, 'UPDATE envios SET status=?, excluido_por=NULL, excluido_em=NULL, status_anterior=NULL WHERE id=?', [voltar, id]);
  await registrarEvento(env, id, 'excluido', voltar, usuario.id, 'Restaurado da lixeira');
  return { message: `Envio restaurado como ${voltar}` };
});

rota('DELETE', '/api/envios/:id/purga', async (env, req, id) => {
  const usuario = await authUsuario(env, req);
  if (!usuario.admin) throw new Http(403, 'Apenas administradores');
  const [n] = await execute(env, "DELETE FROM envios WHERE id=? AND status='excluido'", [id]);
  if (n === 0) throw new Http(404, 'Envio nao encontrado na lixeira');
  await execute(env, 'DELETE FROM eventos WHERE envio_id=?', [id]);
  await execute(env, 'DELETE FROM rastreios WHERE envio_id=?', [id]);
  return { message: 'Envio removido permanentemente' };
});

rota('POST', '/api/envios/:id/rastrear', async (env, req, id) => {
  const usuario = await authOpcional(env, req);
  let row = await fetchOne(env, "SELECT * FROM envios WHERE id = ? AND status <> 'excluido'", [id]);
  if (!row) throw new Http(404, 'Envio nao encontrado');
  const cache = await fetchOne(env, 'SELECT * FROM rastreios WHERE envio_id = ?', [id]);
  const forcar = !!(await corpo(req)).forcar;
  if (cache && !forcar && cacheValido(env, cache)) return rastreioResposta(row, cache, true);
  let res;
  try { res = await consultarRastreio(env, row.codigo); }
  catch (e) {
    /* provedor fora do ar: mostra a ultima consulta boa em vez de erro */
    if (cache && e instanceof Http) return rastreioResposta(row, cache, true, e.detail);
    throw e;
  }
  const novo = { situacao: res.situacao, carrier: res.carrier, eventos: JSON.stringify(res.eventos), consultado_em: agoraIso() };
  const args = [novo.situacao, novo.carrier, novo.eventos, novo.consultado_em, id];
  const [n] = await execute(env, 'UPDATE rastreios SET situacao=?, carrier=?, eventos=?, consultado_em=? WHERE envio_id=?', args);
  if (n === 0) await execute(env, 'INSERT INTO rastreios (situacao,carrier,eventos,consultado_em,envio_id) VALUES (?,?,?,?,?)', args);
  /* so avanca para "entregue": pendente/a_caminho continuam sob controle de quem notifica o cliente */
  let atualizou = false;
  if (res.situacao === 'entregue' && ['pendente', 'a_caminho'].includes(row.status)) {
    await execute(env, "UPDATE envios SET status='entregue', notificado=1, atualizado_em=? WHERE id=?", [agoraIso(), id]);
    await registrarEvento(env, id, row.status, 'entregue', usuario.id || null, 'rastreio automatico');
    row = { ...row, status: 'entregue' };
    atualizou = true;
  }
  return rastreioResposta(row, novo, false, res.mensagem, atualizou);
});

rota('GET', '/api/envios/:id/eventos', async (env, req, id) => {
  await authOpcional(env, req);
  return { eventos: await fetchAll(env, 'SELECT * FROM eventos WHERE envio_id = ? ORDER BY id DESC LIMIT 50', [id]) };
});

rota('POST', '/api/notificacoes', async (env, req) => {
  await authOpcional(env, req);
  const item = await corpo(req);
  if (typeof item.codigo !== 'string') throw new Http(422, 'codigo obrigatorio');
  const codigo = validarCodigo(item.codigo);
  if (String(item.canal || 'email').trim().toLowerCase() === 'whatsapp')
    return { success: false, fallback: true, message: 'WhatsApp via wa.me' };
  const row = await fetchOne(env, 'SELECT * FROM envios WHERE codigo = ?', [codigo]);
  if (!row) throw new Http(404, 'Codigo nao cadastrado');
  const destino = String(row.email || '').trim();
  if (!destino) return { success: false, fallback: true, message: 'Sem e-mail cadastrado' };
  const html = String(item.mensagem || '').trim()
    || montarHtmlEmail(env, row.destinatario, codigo, row.descricao || '', dataEnvioBr(row.criado_em));
  if (await enviarEmail(env, destino, item.assunto || `${E_PACK} Correios — Código de Rastreio: ${codigo}`, html)) {
    await execute(env, "UPDATE envios SET status='a_caminho', notificado=1 WHERE codigo=?", [codigo]);
    return { success: true, result: { enviado: true, email: destino } };
  }
  return { success: false, fallback: true, message: 'SMTP nao configurado — usar mailto:' };
});

rota('POST', '/api/notificacoes/massa', async (env, req) => {
  await authOpcional(env, req);
  if (String((await corpo(req)).canal || 'email').toLowerCase() !== 'email') throw new Http(422, 'Massa disponivel para e-mail');
  if (!smtpConfigurado(env)) throw new Http(422, 'SMTP nao configurado');
  const rows = await fetchAll(env, "SELECT * FROM envios WHERE status='pendente' AND email<>'' ORDER BY id");
  let enviadas = 0;
  const falhas = [];
  for (const r of rows) {
    const html = montarHtmlEmail(env, r.destinatario || '', r.codigo || '', r.descricao || '', dataEnvioBr(r.criado_em));
    if (await enviarEmail(env, String(r.email || '').trim(), `${E_PACK} Correios - Codigo: ${r.codigo}`, html)) {
      await execute(env, "UPDATE envios SET status='a_caminho', notificado=1, atualizado_em=? WHERE id=?", [agoraIso(), r.id]);
      enviadas++;
    } else falhas.push(r.codigo);
  }
  return { message: `${enviadas} enviado(s)`, enviadas, falhas };
});

rota('POST', '/api/auth/registrar', async (env, req) => {
  const item = await corpo(req);
  if (typeof item.nome !== 'string' || typeof item.email !== 'string' || typeof item.senha !== 'string')
    throw new Http(422, 'nome, email e senha sao obrigatorios');
  const primeiro = await contarUsuarios(env) === 0;
  const admin = primeiro ? true : !!item.admin;
  if (!primeiro) {
    let s;
    try { s = await authUsuario(env, req); } catch (e) { throw new Http(403, 'Registro restrito'); }
    if (!s.admin) throw new Http(403, 'Apenas administradores');
  }
  const email = item.email.trim().toLowerCase();
  if (!REGEX_EMAIL.test(email)) throw new Http(422, 'E-mail invalido');
  if (!item.nome.trim()) throw new Http(422, 'Nome obrigatorio');
  if (item.senha.length < 8) throw new Http(422, 'Senha muito curta (minimo 8)');
  let uid;
  try {
    [, uid] = await execute(env, 'INSERT INTO usuarios (nome,email,senha_hash,admin) VALUES (?,?,?,?)',
      [item.nome.trim(), email, await hashSenha(item.senha), admin ? 1 : 0]);
  } catch (e) { throw new Http(409, 'E-mail ja cadastrado'); }
  return { message: 'Usuario criado', id: uid, admin };
});

rota('POST', '/api/auth/login', async (env, req) => {
  const item = await corpo(req);
  if (typeof item.email !== 'string' || typeof item.senha !== 'string') throw new Http(422, 'email e senha sao obrigatorios');
  /* anti brute-force: no maximo LOGIN_MAX_TENT falhas por IP dentro da janela */
  const ip = req.headers.get('CF-Connecting-IP') || 'desconhecido';
  const agora = Math.floor(Date.now() / 1000), janela = num(env.LOGIN_JANELA_SEG, 300);
  const falhas = Number((await fetchOne(env, 'SELECT COUNT(*) AS n FROM login_falhas WHERE ip = ? AND ts > ?', [ip, agora - janela]))?.n || 0);
  if (falhas >= num(env.LOGIN_MAX_TENT, 10)) throw new Http(429, 'Muitas tentativas. Aguarde alguns minutos.');
  const row = await fetchOne(env, 'SELECT * FROM usuarios WHERE email = ? AND ativo = 1', [item.email.trim().toLowerCase()]);
  if (!row || !(await verificarSenha(item.senha, row.senha_hash))) {
    await execute(env, 'INSERT INTO login_falhas (ip, ts) VALUES (?, ?)', [ip, agora]);
    throw new Http(401, 'E-mail ou senha incorretos');
  }
  /* aproveita o login para a faxina: falhas antigas e sessoes vencidas */
  await env.DB.batch([
    env.DB.prepare('DELETE FROM login_falhas WHERE ip = ? OR ts <= ?').bind(ip, agora - janela),
    env.DB.prepare('DELETE FROM sessoes WHERE expira_em <= ?').bind(agoraIso()),
  ]);
  const token = hex(crypto.getRandomValues(new Uint8Array(32)));
  const expira = iso(new Date(Date.now() + num(env.SESSAO_DIAS, 7) * 86400000));
  await execute(env, 'INSERT INTO sessoes (token,usuario_id,expira_em) VALUES (?,?,?)', [token, row.id, expira]);
  return { token, user: { id: row.id, nome: row.nome, email: row.email, admin: !!row.admin } };
});

rota('POST', '/api/auth/logout', async (env, req) => {
  const token = bearer(req);
  if (token) { try { await execute(env, 'DELETE FROM sessoes WHERE token = ?', [token]); } catch (e) { /* tanto faz */ } }
  return { message: 'Sessao encerrada' };
});

rota('POST', '/api/auth/trocar-senha', async (env, req) => {
  const usuario = await authUsuario(env, req);
  const item = await corpo(req);
  if (typeof item.senha_atual !== 'string' || typeof item.senha_nova !== 'string') throw new Http(422, 'senha_atual e senha_nova sao obrigatorias');
  const row = await fetchOne(env, 'SELECT * FROM usuarios WHERE id = ?', [usuario.id]);
  if (!row || !(await verificarSenha(item.senha_atual, row.senha_hash))) throw new Http(401, 'Senha atual incorreta');
  if (item.senha_nova.length < 8) throw new Http(422, 'Senha muito curta (minimo 8)');
  await execute(env, 'UPDATE usuarios SET senha_hash = ? WHERE id = ?', [await hashSenha(item.senha_nova), usuario.id]);
  return { message: 'Senha alterada' };
});

rota('GET', '/api/usuarios', async (env, req) => {
  const usuario = await authUsuario(env, req);
  if (!usuario.admin) throw new Http(403, 'Apenas administradores');
  return { usuarios: await fetchAll(env, 'SELECT id, nome, email, admin, ativo, criado_em FROM usuarios ORDER BY id') };
});

rota('PATCH', '/api/usuarios/:id', async (env, req, uid) => {
  const usuario = await authUsuario(env, req);
  if (!usuario.admin) throw new Http(403, 'Apenas administradores');
  if (!(await fetchOne(env, 'SELECT id FROM usuarios WHERE id = ?', [uid]))) throw new Http(404, 'Usuario nao encontrado');
  const payload = await corpo(req), sets = [], args = [];
  if (payload.admin != null) { sets.push('admin = ?'); args.push(payload.admin ? 1 : 0); }
  if (payload.ativo != null) {
    if (uid === usuario.id && !payload.ativo) throw new Http(422, 'Voce nao pode desativar a si mesmo');
    sets.push('ativo = ?'); args.push(payload.ativo ? 1 : 0);
  }
  if (!sets.length) throw new Http(422, 'Nada para atualizar');
  await execute(env, `UPDATE usuarios SET ${sets.join(', ')} WHERE id = ?`, [...args, uid]);
  if (payload.ativo != null && !payload.ativo) await execute(env, 'DELETE FROM sessoes WHERE usuario_id = ?', [uid]);
  return { message: 'Usuario atualizado' };
});

rota('GET', '/api/estatisticas', async (env, req) => {
  await authOpcional(env, req);
  const mapa = {};
  for (const r of await fetchAll(env, 'SELECT status, COUNT(*) AS n FROM envios GROUP BY status')) mapa[r.status] = Number(r.n);
  return {
    total: Object.values(mapa).reduce((a, b) => a + b, 0), pendente: mapa.pendente || 0,
    a_caminho: mapa.a_caminho || 0, entregue: mapa.entregue || 0,
  };
});

rota('GET', '/api/backup', async (env, req) => {
  const usuario = await authUsuario(env, req);
  if (!usuario.admin) throw new Http(403, 'Apenas administradores');
  throw new Http(400, 'Backup de arquivo disponivel apenas com SQLite (D1: use "wrangler d1 export rastreio-facil --remote")');
});

/* ---------- arquivos estaticos: a pasta static/ e publicada na raiz dos assets ---------- */
async function estatico(env, req, caminho, cache){
  const r = await env.ASSETS.fetch(new Request(new URL(caminho, req.url), { method: 'GET', headers: req.headers }));
  const resp = new Response(r.body, r);
  if (cache) resp.headers.set('Cache-Control', cache);
  return resp;
}

function cors(env, req){
  const origens = String(env.CORS_ORIGINS || '').split(',').map(o => o.trim()).filter(Boolean);
  const origem = req.headers.get('Origin');
  if (!origem || !(origens.includes('*') || origens.includes(origem))) return {};
  return {
    'Access-Control-Allow-Origin': origens.includes('*') ? '*' : origem,
    'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    Vary: 'Origin',
  };
}

export default {
  async fetch(req, env){
    const url = new URL(req.url), p = url.pathname;
    if (p.startsWith('/api/')) {
      const ch = cors(env, req);
      if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: ch });
      let caminhoExiste = false;
      for (const r of rotas) {
        const m = p.match(r.rx);
        if (!m) continue;
        caminhoExiste = true;
        if (r.metodo !== req.method) continue;
        try {
          return json(await r.fn(env, req, m[1] ? Number(m[1]) : undefined, url), 200, ch);
        } catch (e) {
          if (e instanceof Http) return json({ detail: e.detail }, e.status, ch);
          console.log('[erro]', p, e && e.stack || e);
          return json({ detail: 'Erro interno' }, 500, ch);
        }
      }
      return caminhoExiste ? json({ detail: 'Method Not Allowed' }, 405, ch) : json({ detail: 'Not Found' }, 404, ch);
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return json({ detail: 'Method Not Allowed' }, 405);
    /* HTML sempre sem cache: o navegador pega os ?v= mais novos do JS */
    if (p === '/' || p === '/main' || p === '/login') return estatico(env, req, '/index.html', 'no-store');
    if (p.startsWith('/static/')) {
      const cache = p.startsWith('/static/libs/') || p.startsWith('/static/img/')
        ? 'public, max-age=31536000, immutable'
        : (/\.(js|css|html|json)$/.test(p) ? 'no-cache, must-revalidate' : '');
      return estatico(env, req, p.slice('/static'.length), cache);
    }
    return json({ detail: 'Not Found' }, 404);
  },
};
