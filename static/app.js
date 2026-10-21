/* Rastreio Facil — UI moderna dark */
/* API: quando o backend serve a própria página usamos path relativo (qualquer host/porta);
   se a página vier de outra origem (Live Server, file://) falamos com o backend :3000.
   NÃO trocar por '/api' fixo sem desativar o Live Server, senão os POSTs caem no Live Server (405).
   Usamos uma LISTA de portas do Live Server em vez de uma porta fixa: assim não quebra quando o
   Live Server troca de porta (ex.: 5502 no .vscode/settings.json). */
const _portasLiveServer = ['5500','5501','5502','5503'];
const API = (location.protocol.startsWith('http') && !_portasLiveServer.includes(location.port))
  ? '/api' : 'http://localhost:3000/api';
/* anti-spam de console: quando o backend esta fora do ar, o navegador loga
   ERR_CONNECTION_REFUSED sozinho (nao da para suprimir via JS), entao reduzimos
   as tentativas ao minimo: 1 check no boot + backoff 5s/10s/20s/30s/60s.
   Assim o console mostra ~6 linhas em 2 min em vez de dezenas. */
let _semBackendDesde = 0, _tentativasOff = 0;
function _esperaBackoff(){
  _tentativasOff++;
  if(_tentativasOff <= 1) return 5000;
  if(_tentativasOff === 2) return 10000;
  if(_tentativasOff === 3) return 20000;
  if(_tentativasOff === 4) return 30000;
  return 60000;
}
function _backendVoltou(){ _tentativasOff = 0; _semBackendDesde = 0; }
const $ = id => document.getElementById(id);
const state = { envios: [], db: {}, token: localStorage.getItem('rf_token')||'', adminEmail: 'admin@admin.com' };
const APP_V = '29'; /* versão do front: se o servidor tiver outra, a página se recarrega sozinha */
window.APP_V = APP_V; /* facilita conferir a versão no console: window.APP_V */
/* ===== erros visíveis: nada de falhar em silêncio =====
   Se qualquer coisa quebrar, o problema aparece na barra vermelha do rodapé
   (antes só aparecia no console, e o usuário achava que "não fez nada"). */
function _erroFatal(m){
  var d = document.getElementById('erro-fatal');
  if(!d){
    d = document.createElement('div'); d.id = 'erro-fatal';
    d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#3d1a1a;color:#ffb3ad'
      + ';border-top:2px solid #8b2b2b;padding:10px 14px;font:13px system-ui;white-space:pre-wrap';
    (document.body||document.documentElement).appendChild(d);
  }
  d.textContent = 'ERRO: ' + m;
}
window.addEventListener('error', function(e){ _erroFatal((e.message||'erro') + (e.filename ? ' — linha ' + e.lineno : '')); });
window.addEventListener('unhandledrejection', function(e){
  var m = String((e.reason && e.reason.message) || e.reason || '');
  if(/fetch|network|conex|recus|Failed to fetch|load failed/i.test(m)) return; /* ruído esperado do modo offline */
  _erroFatal('promessa rejeitada: ' + m);
});
/* ===== modo offline: salva no navegador quando o backend não responde ===== */
const LSK_ENVIOS = 'rf_envios_locais';
function isNetError(e){ return e instanceof TypeError || /fetch|network|conex|recus/i.test(String((e&&e.message)||'')); }
function lerLocais(){ try{ return JSON.parse(localStorage.getItem(LSK_ENVIOS)||'[]'); }catch(e){ return []; } }
function gravarLocais(l){ try{ localStorage.setItem(LSK_ENVIOS, JSON.stringify(l)); }catch(e){ toast('Erro ao salvar no navegador: '+e.message); } }
function idLocal(){ return -Date.now(); }
function linkRastreio(c){ return 'https://rastreamento.correios.com.br/app/index.php?objeto='+encodeURIComponent(c); }
const NOME_EQUIPE = localStorage.getItem('rf_equipe') || 'Equipe Rastreio Fácil';
function dataEnvioBR(e){
  const raw = e && e.criado_em;
  if(raw){
    const m = String(raw).slice(0,10);
    if(/^\d{4}-\d{2}-\d{2}$/.test(m)){ const p = m.split('-'); return p[2]+'/'+p[1]+'/'+p[0]; }
  }
  return new Date().toLocaleDateString('pt-BR');
}
/* data/hora local: usada nos envios criados offline (assim a data não muda a cada render) */
function agoraLocal(){
  const d = new Date(), p = n => String(n).padStart(2,'0');
  return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
}
/* emojis via escape Unicode (imunes a problema de codificação do arquivo/servidor) */
const E_PACK = '\u{1F4E6}'; /* 📦 */
const E_WAVE = '\u{1F44B}'; /* 👋 */
const E_LIST = '\u{1F4CB}'; /* 📋 */
const E_LINK = '\u{1F517}'; /* 🔗 */
function montarMsgRastreio(e){
  const nome = (e.destinatario||'cliente').trim();
  const link = e.link || linkRastreio(e.codigo);
  const sep = '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500';
  const linhas = [
    E_PACK+' *CORREIOS — CÓDIGO DE RASTREIO*',
    '',
    'Olá, *'+nome+'*! Tudo bem? '+E_WAVE,
    '',
    'Sua correspondência foi postada e já está em rota de entrega.',
    '',
    sep,
    E_LIST+' *DETALHES DO ENVIO*',
    '',
    '▸ *Código:* '+e.codigo
  ];
  if((e.descricao||'').trim()) linhas.push('▸ *Descrição:* '+e.descricao.trim());
  linhas.push('▸ *Data de Envio:* '+dataEnvioBR(e));
  linhas.push(sep, '', E_LINK+' *ACOMPANHE EM TEMPO REAL*', link, '',
    'Qualquer dúvida, estamos à disposição!', '', 'Atenciosamente,', '*'+NOME_EQUIPE+'*');
  return linhas.join('\n');
}
function montarMsgTexto(e){ return montarMsgRastreio(e).replace(/\*/g,''); }
/* copia para a área de transferência (texto puro — imune a problemas de encoding de URL) */
async function copiarTexto(t){
  try{ await navigator.clipboard.writeText(t); return true; }
  catch(e){
    try{
      const ta = document.createElement('textarea');
      ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand('copy'); ta.remove(); return ok;
    }catch(e2){ return false; }
  }
}
const headers = () => state.token ? {'Content-Type':'application/json','Authorization':'Bearer '+state.token} : {'Content-Type':'application/json'};
function toast(m, acao){
  const msgEl = $('toast-msg');
  const toastEl = $('toast');
  if(typeof m === 'object' && m !== null){
    acao = m.acao;
    m = m.msg || m.message || '';
  }
  msgEl.textContent = m;
  // remove botão de ação anterior se houver
  const oldBtn = toastEl.querySelector('.toast-action');
  if(oldBtn) oldBtn.remove();
  if(acao && acao.texto && typeof acao.fn === 'function'){
    const btn = document.createElement('button');
    btn.className = 'toast-action';
    btn.textContent = acao.texto;
    btn.style.marginLeft = '12px';
    btn.style.padding = '4px 10px';
    btn.style.border = 'none';
    btn.style.borderRadius = '4px';
    btn.style.background = '#2563eb';
    btn.style.color = '#fff';
    btn.style.cursor = 'pointer';
    btn.style.fontSize = '12px';
    btn.onclick = ()=>{ acao.fn(); toastEl.classList.remove('show'); };
    msgEl.appendChild(btn);
  }
  toastEl.classList.add('show');
  clearTimeout(window._t);
  window._t = setTimeout(()=>toastEl.classList.remove('show'), 5000); // mais tempo para ler + clicar desfazer
}
function uiStatus(e){ const s=(e.status||'pendente'); if(s==='entregue') return 'entregue'; if(s==='a_caminho') return 'a_caminho'; if(s==='excluido') return 'excluido'; return 'pendente'; }
function badge(s){ return s==='entregue' ? '<span class="badge b-entregue">entregue</span>' : s==='a_caminho' ? '<span class="badge b-a_caminho">a caminho</span>' : s==='excluido' ? '<span class="badge badge--excluido">lixeira</span>' : '<span class="badge b-pendente">pendente</span>'; }
function esc(s){ const m = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}; return String(s ?? '').replace(/[&<>"']/g, c=>m[c]); }
/* validação (topo: boot() usa estas funções/consts) */
const RX_COD = /^[A-Z]{2}\d{9}BR$/;
const RX_MAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
function limparCodigo(v){
  v = String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,13);
  let out = '';
  for(let i=0;i<v.length;i++){
    const c = v[i];
    if((i<2 || i>=11) && /[A-Z]/.test(c)) out += c;
    else if(i>=2 && i<11 && /\d/.test(c)) out += c;
  }
  return out;
}
function codigoMsg(v){
  if(!v) return {txt:'Formato: 2 letras + 9 números + BR', cls:'field-msg'};
  if(v.length < 2) return {txt:'Comece com 2 letras (ex: AA...)', cls:'field-msg err'};
  if(v.length < 11) return {txt:'Falta: '+(11-v.length)+' número(s) após as 2 letras', cls:'field-msg err'};
  if(v.length < 13) return {txt:'Falta: '+(13-v.length)+' letra(s) no final (BR)', cls:'field-msg err'};
  if(!/BR$/.test(v)) return {txt:'✕ O final deve ser BR (ex: AA123456789BR)', cls:'field-msg err'};
  return {txt:'✓ Formato válido', cls:'field-msg ok'};
}
function erroEmail(v){
  const e = String(v||'').trim();
  if(!e) return '';
  if(/\s/.test(e)) return 'não pode ter espaços';
  if(!e.includes('@')) return 'isso não é um e-mail: falta o @ (ex: nome@dominio.com)';
  const partes = e.split('@');
  if(partes.length > 2) return 'só pode ter um @';
  const local = partes[0], dom = partes[1];
  if(!local) return 'falta o nome antes do @ (ex: nome@dominio.com)';
  if(!dom) return 'falta o domínio depois do @ (ex: nome@dominio.com)';
  if(!dom.includes('.')) return 'o domínio precisa ter um ponto (ex: dominio.com)';
  if(dom.startsWith('.') || dom.endsWith('.') || dom.split('.').some(p=>!p)) return 'há um ponto sobrando no domínio';
  if(!RX_MAIL.test(e)) return 'formato inválido (ex: nome@dominio.com)';
  return '';
}
function codigoValido(v){ return RX_COD.test(String(v||'').toUpperCase().trim()); }
function foneDigitos(v){ let d = String(v||'').replace(/\D/g,''); if(d.startsWith('0055')) d = '55'+d.slice(4); if(d.startsWith('0')&&d.length>1) d = d.slice(1); if(d.startsWith('55') && (d.length===12||d.length===13)) d = d.slice(2); return d; }
function foneValido(v){ if(!String(v||'').trim()) return true; const d = foneDigitos(v); return d.length===10 || d.length===11; }
async function api(path, opt={}){
  const r = await fetch(API+path, {...opt, headers:{...headers(), ...(opt.headers||{})}});
  let d = {};
  /* resposta que não é JSON = não é o nosso backend (ex.: Live Server devolvendo HTML de 404/405).
     Lançamos TypeError para isso contar como erro de rede e cair no modo offline (salva no navegador). */
  try{ d = await r.json(); }
  catch(e){ throw new TypeError('Sem resposta JSON da API em '+API+' (status '+r.status+')'); }
  if(r.status===401 && path!=='/auth/login' && path!=='/auth/estado'){ pedirLogin(); }
  if(!r.ok){
    const det = d.erros ? ' — '+d.erros.slice(0,3).join('; ') : '';
    throw new Error((d.message || (typeof d.detail === 'string' && d.detail) || ('Erro '+r.status)) + det);
  }
  return d;
}
/* sessão: abre o login automaticamente quando o servidor pede autenticação */
function pedirLogin(msg){
  const sessaoExpirou = !!state.token;
  if(sessaoExpirou){ state.token=''; state.usuarioId = null; localStorage.removeItem('rf_token'); }
  if(window._loginPedido) return;
  window._loginPedido = true;
  const box = $('modal-login'); if(box) box.hidden = false;
  const err = $('l-err');
  if(err){ err.textContent = msg || (sessaoExpirou ? 'Sua sessão expirou. Entre novamente para ver os envios do banco de dados.' : 'Sessão necessária: entre como o admin para ver e cadastrar envios no banco de dados.'); err.hidden = false; }
  const em = $('l-email-fix'); if(em) em.textContent = state.adminEmail;
  const sn = $('l-senha'); if(sn) sn.focus();
}
async function checkDB(){
  try{
    const d = await api('/db-status');
    const acabouDeVoltar = (state.online === false); /* estava offline e o backend respondeu: acabou de voltar */
    state.online = true;
    _backendVoltou();
    if(acabouDeVoltar) checarVersao(); /* confere a versão do front na hora, sem esperar os 15s do intervalo */
    state.db = d;
    const pill = $('db-pill');
    const nomeDb = d.driver === 'd1' ? 'Cloudflare D1' : 'Postgres';
    if(!d.configured){
      pill.textContent = 'banco local (sem Postgres)'; pill.className = 'pill ok';
    } else if(!d.connected){
      pill.textContent = nomeDb+' com erro'; pill.className = 'pill bad';
      /* o detalhe muda a cada falha: avisa uma vez por mensagem nova (sem spammar a cada retry) */
      const detalhe = d.error || 'verifique a URL.';
      const chave = 'pg:' + detalhe;
      if(state.ultimoAvisoDb !== chave){ state.ultimoAvisoDb = chave; toast(nomeDb+' com erro (' + detalhe + ')'); }
    } else {
      pill.textContent = nomeDb+' conectado'; pill.className = 'pill ok';
    }
  }catch(e){
    const estavaOffline = (state.online === false);
    state.online = false;
    $('db-pill').textContent = 'modo offline — salvando no navegador'; $('db-pill').className = 'pill bad';
    /* sem bloco de alerta na tela: a pílula do cabeçalho já mostra o estado e a reconexão é automática;
       o toast aparece só na transição (1ª vez que o backend falha), não a cada tentativa */
    if(!estavaOffline) toast('Servidor fora do ar — gravando neste navegador. Sincroniza sozinho quando ele voltar.');
    /* agenda a proxima tentativa com backoff (5s→10s→20s→30s→60s) em vez de martelar o servidor */
    clearTimeout(window._retryT);
    const espera = _esperaBackoff();
    _semBackendDesde = _semBackendDesde || Date.now();
    window._retryT = setTimeout(()=>{ if(state.online === false) load(); }, espera);
  }
}

/* proteção anti-loop: se alguma aba antiga ficar repetindo o ciclo, o servidor não é martelado e a tela não trava */
let _carregando = false, _ultimoCiclo = 0, _pendente = false, _timerPend = null;
async function load(){
  if(_carregando){ _pendente = true; return; }
  const espera = 700 - (Date.now() - _ultimoCiclo);
  if(espera > 0){
    _pendente = true;
    clearTimeout(_timerPend);
    _timerPend = setTimeout(()=>{ if(_pendente){ _pendente = false; load(); } }, espera);
    return;
  }
  _ultimoCiclo = Date.now();
  _carregando = true;
  try{
  await checkDB();
  let remotos = [];
  if(!state.online){ $('btn-backup').hidden = true; }
  if(state.online){
    // v28: admin unico — o servidor informa o e-mail do admin e se o token e de admin
    let autenticado = false;
    try{
      const est = await api('/auth/estado');
      state.admin = !!est.admin;
      if(est.email) state.adminEmail = est.email;
      autenticado = !!state.token && state.admin;
      $('btn-backup').hidden = !state.admin; /* ação reservada a administradores */
      const fix = $('l-email-fix'); if(fix) fix.textContent = state.adminEmail;
      if(!state.token) pedirLogin('Entre com o admin ('+state.adminEmail+') para ver e cadastrar envios no banco de dados.');
    }catch(e){}
    // v28: o banco só aceita requisições autenticadas (admin unico)
    const podeBanco = autenticado;
    // sincroniza envios cadastrados no modo offline (só quando o banco aceita)
    const pend = lerLocais();
    if(pend.length && podeBanco){
      let sinc = 0, desc = 0;
      for(const it of pend){
        try{
          await api('/envios',{method:'POST',body:JSON.stringify({destinatario:it.destinatario,codigo:it.codigo,email:it.email,celular:it.celular,descricao:it.descricao,status:it.status})});
          sinc++;
        }catch(err){
          if(isNetError(err)) break; /* servidor caiu: para e mantém o resto */
          desc++; /* erro de validação (422): item não vai passar nunca — descarta */
        }
      }
      if(sinc || desc){
        gravarLocais(pend.slice(sinc+desc));
        toast(sinc+' envio(s) sincronizado(s)!'+(desc?' ('+desc+' descartado(s) por dados inválidos)':''));
      }
    }
    if(podeBanco){
      /* paginação: o servidor devolve no máx. 500/página — busca TODAS as páginas
         (antes: só a 1ª, que o servidor corta em 200; +200 envios não apareciam na lista) */
      try{
        remotos = []; let pagina = 1;
        for(;;){
          const dp = await api('/envios?page='+pagina+'&limit=500');
          const itens = dp.envios || [];
          remotos = remotos.concat(itens);
          if(itens.length < 500 || remotos.length >= (dp.total||0)) break;
          pagina++;
        }
      }catch(e){ remotos = []; }
      /* correcao v25: admin carrega tambem a lixeira. A listagem padrao da API
         (sem "status") exclui status='excluido', entao antes o card "Lixeira" ficava
         sempre vazio e os botoes "Restaurar"/"Apagar def." eram inalcancaveis.
         v29: guardamos o total que a propria pagina da lixeira ja devolveu
         (dl.total) — antes era preciso um request extra so pra contar. */
      if(state.admin){
        try{
          let pagina = 1, lidos = 0;
          for(;;){
            const dl = await api('/envios?status=excluido&page='+pagina+'&limit=500');
            const itens = dl.envios || [];
            remotos = remotos.concat(itens); lidos += itens.length;
            state.lixeiraTotal = dl.total || 0;
            if(itens.length < 500 || lidos >= (dl.total||0)) break;
            pagina++;
          }
        }catch(e){}
      }else{
        state.lixeiraTotal = 0;   /* não-admin: zera (o card fica escondido) */
      }
    }
  }
  state.envios = [...remotos, ...lerLocais()];
  // mostra/oculta stat de lixeira conforme admin
  const statLix = $('stat-lix');
  if(statLix) statLix.hidden = !state.admin;
  render();
  } finally { _carregando = false; if(_pendente){ _pendente = false; load(); } }
}
/* ===== melhoria v22: filtro reutilizável e destaque dos cards =====
   v29: filtrados() agora faz UMA passagem só e devolve também os contadores dos
   cards. Antes o render() rodava 5 .filter() separados sobre state.envios
   (4 cards + a lista) a cada busca — 5x o trabalho a cada tecla digitada. */
function filtrados(){
  const q = ($('f-busca').value || '').toLowerCase();
  const f = $('f-filtro').value;
  const lista = [];
  const cont = { total:0, pendente:0, a_caminho:0, entregue:0, excluido:0 };
  for(const e of state.envios){
    const s = uiStatus(e);
    if(s==='excluido') cont.excluido++;
    else cont.total++;
    if(s==='pendente') cont.pendente++;
    else if(s==='a_caminho') cont.a_caminho++;
    else if(s==='entregue') cont.entregue++;
    // "todos" mostra os ativos (a lixeira tem o proprio filtro/card)
    const okF = f === 'todos' ? s !== 'excluido' : s === f;
    const okQ = !q || (e.destinatario + ' ' + e.codigo + ' ' + (e.descricao || '')).toLowerCase().includes(q);
    if(okF && okQ) lista.push(e);
  }
  return { lista, cont };
}
/* v29: a lista não renderiza tudo de uma vez. Com centenas de envios o innerHTML
   gigante travava a rolagem (cada linha tem até 9 botões). Renderizamos blocos de
   120 e o usuário pede mais com o botão "Carregar mais". */
const PAGINA_LINHAS = 120;
let _listaExibida = PAGINA_LINHAS;   /* quantas linhas já estão no DOM */
function render(){
  const { lista, cont } = filtrados();
  const isAdmin = !!state.admin;
  $('st-total').textContent = cont.total;
  $('st-pend').textContent = cont.pendente;
  $('st-cam').textContent = cont.a_caminho;
  $('st-ent').textContent = cont.entregue;
  $('st-lix').textContent = state.lixeiraTotal || cont.excluido;
  document.querySelectorAll('.stat[data-filtro]').forEach(c=>c.classList.toggle('ativo', c.dataset.filtro === $('f-filtro').value));
  $('list-count').textContent = lista.length;
  $('empty').style.display = lista.length ? 'none' : 'block';
  const visiveis = lista.slice(0, _listaExibida);
  $('lista').innerHTML = visiveis.map(e=>{
    const s = uiStatus(e);
    const contato = [e.email, e.celular ? mascararFoneBR(e.celular) : ''].filter(Boolean).join(' • ') || 'sem contato';
    const autor = e.criado_por_nome ? '👤 '+esc(e.criado_por_nome) : '';
    const delInfo = (s==='excluido' && isAdmin && e.excluido_por_nome) ? ' 🗑️ por '+esc(e.excluido_por_nome) : '';
    const restoredFrom = (s==='excluido' && e.status_anterior) ? ' (era: '+esc(e.status_anterior)+')' : '';
    return '<div class="item" data-id="'+e._id+'">'
      +'<div class="item-top"><b>'+esc(e.destinatario)+'</b>'+badge(s)+'</div>'
      +'<code>'+esc(e.codigo)+'</code>'
      +'<small class="autor">'+esc(contato)+(e.descricao ? ' — '+esc(e.descricao) : '')+'</small>'
      +'<small class="meta">'+autor+delInfo+restoredFrom+'</small>'
      +'<div class="item-actions">'
      +(s==='excluido' && isAdmin ? '<button class="chip success" data-act="restaurar">♻️ Restaurar</button>' : '')
      +(s!=='a_caminho' && s!=='excluido' ? '<button class="chip" data-act="a_caminho">A caminho</button>' : '')
      +(s!=='entregue' && s!=='excluido' ? '<button class="chip" data-act="entregue">Entregue</button>' : '')
      +(s!=='pendente' && s!=='excluido' ? '<button class="chip" data-act="pendente">Pendente</button>' : '')
      +(s!=='excluido' ? '<button class="chip" data-act="wa">WhatsApp</button>' : '')
      +(s!=='excluido' ? '<button class="chip" data-act="mail">E-mail</button>' : '')
      +(s!=='excluido' ? '<button class="chip" data-act="track">Rastrear</button>' : '')
      +(s!=='excluido' ? '<button class="chip" data-act="edit">✏️ Editar</button>' : '')
      +(s!=='excluido' ? '<button class="chip danger" data-act="del">Excluir</button>' : '')
      +(s==='excluido' && isAdmin ? '<button class="chip danger" data-act="purga">🗑️ Apagar def.</button>' : '')
      +'</div></div>';
  }).join('');
  /* botão "carregar mais" (só aparece se ainda há linhas fora da tela) */
  const btn = $('btn-mais');
  const restantes = lista.length - visiveis.length;
  if(btn){
    btn.hidden = restantes <= 0;
    btn.textContent = 'Carregar mais (' + restantes + ' restantes)';
  }
}
document.getElementById('lista').addEventListener('click', async ev=>{
  const b = ev.target.closest('[data-act]'); if(!b) return;
  const card = ev.target.closest('.item'); const id = card && card.dataset.id;
  const e = state.envios.find(x=>String(x._id)===String(id));
  if(!e) return;
  const act = b.dataset.act;
  const local = !!e._local;
  const atualizarLocal = fn=>{ const l = lerLocais(); const it = l.find(x=>String(x._id)===String(id)); if(it){ fn(it); gravarLocais(l); } };
  try{
    if(act==='edit'){ abrirEdicao(id, e, local); return; }
    if(act==='del'){
      // Confirmação rica com detalhes do envio
      const detalhes = [
        'Destinatário: ' + e.destinatario,
        'Código: ' + e.codigo,
        'Status: ' + uiStatus(e),
        'Criado por: ' + (e.criado_por_nome || '—'),
        '',
        'O envio será movido para a LIXEIRA (pode ser restaurado pelo admin).',
        'Confirma a exclusão?'
      ].join('\n');
      if(!confirm(detalhes)) return;
      if(local){
        gravarLocais(lerLocais().filter(x=>String(x._id)!==String(id)));
        toast('Excluído (local).');
      }else{
        await api('/envios/'+id,{method:'DELETE'});
        // Toast com ação "Desfazer" (restaura via admin endpoint)
        const msg = 'Envio movido para lixeira';
        const acao = {texto: 'Desfazer', fn: async ()=>{
          try{
            await api('/envios/'+id+'/restaurar',{method:'POST'});
            toast('Envio restaurado!');
            await load();
          }catch(err){ toast('Erro ao restaurar: '+err.message); }
        }};
        toast(msg, acao);
      }
    }
    else if(act==='restaurar'){
      if(!confirm('Restaurar este envio da lixeira?')) return;
      await api('/envios/'+id+'/restaurar',{method:'POST'});
      toast('Envio restaurado!');
    }
    else if(act==='purga'){
      if(!confirm('APAGAR DEFINITIVAMENTE este envio?\n\nEsta ação NÃO PODE SER DESFEITA.\nO histórico de eventos também será removido.')) return;
      await api('/envios/'+id+'/purga',{method:'DELETE'});
      toast('Envio removido permanentemente.');
    }
    else if(act==='pendente'||act==='a_caminho'||act==='entregue'){
      if(local){ atualizarLocal(it=>{ it.status = act; it.notificado = act==='pendente' ? 0 : 1; }); toast('Status atualizado (local).'); }
      else { await api('/envios/'+id+'/status',{method:'PATCH',body:JSON.stringify({status:act})}); toast('Status atualizado.'); }
    }
    else if(act==='track'){
      /* sem backend (envio local/offline) não há como consultar a API: abre o site dos Correios */
      if(local || !state.online){ window.open(e.link||linkRastreio(e.codigo),'_blank'); return; }
      abrirRastreio(id, e); return;
    }
    else if(act==='wa'){
      const fone = (e.celular||'').replace(/\D/g,'');
      if(!fone){ toast('Sem WhatsApp cadastrado.'); return; }
      if(fone.length < 10 || fone.length > 11){ toast('WhatsApp inválido — confira o número (DDD + 8/9 dígitos).'); return; }
      window._waCtx = { fone: fone, id: id, local: local, status: e.status };
      $('wa-msg').value = montarMsgRastreio(e);
      $('modal-wa').hidden = false;
      return;
    }
    else if(act==='mail'){
      if(!e.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.email)){ toast('E-mail inválido ou não cadastrado.'); return; }
      if(local){ window.open('mailto:'+e.email+'?subject='+encodeURIComponent(E_PACK+' Correios — Código de Rastreio: '+e.codigo)+'&body='+encodeURIComponent(montarMsgTexto(e)),'_blank'); toast('Aberto no seu app de e-mail (modo local).'); return; }
      try{
        const r = await api('/notificacoes',{method:'POST',body:JSON.stringify({codigo:e.codigo,canal:'email',mensagem:''})});
        if(r.success) toast('E-mail enviado!');
        else window.open('mailto:'+e.email+'?subject='+encodeURIComponent(E_PACK+' Correios — Código de Rastreio: '+e.codigo)+'&body='+encodeURIComponent(montarMsgTexto(e)),'_blank');
      }catch(err){ window.open('mailto:'+e.email+'?subject='+encodeURIComponent(E_PACK+' Correios — Código de Rastreio: '+e.codigo)+'&body='+encodeURIComponent(montarMsgTexto(e)),'_blank'); }
      await load(); return;
    }
    await load();
  }catch(err){ toast(err.message); }
});
/* modal de rastreio: eventos vindos da API (POST /envios/{id}/rastrear, com cache no servidor) */
function dataHoraBR(s){
  const m = String(s||'').match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}))?/);
  return m ? m[3]+'/'+m[2]+'/'+m[1]+(m[4] ? ' '+m[4] : '') : String(s||'');
}
function abrirRastreio(id, e){
  window._rtCtx = { id: id, link: e.link||linkRastreio(e.codigo) };
  $('rt-codigo').textContent = e.codigo;
  $('modal-rt').hidden = false;
  consultarRastreio(false);
}
async function consultarRastreio(forcar){
  const ctx = window._rtCtx; if(!ctx) return;
  const info = $('rt-info'), err = $('rt-err'), lista = $('rt-lista'), btn = $('btn-rt-atualizar');
  info.textContent = 'Consultando…'; err.hidden = true; lista.innerHTML = '';
  btn.disabled = true;
  try{
    const d = await api('/envios/'+ctx.id+'/rastrear',{method:'POST',body:JSON.stringify({forcar:!!forcar})});
    if(window._rtCtx !== ctx) return; /* trocou de envio enquanto consultava */
    const evs = d.eventos || [];
    lista.className = 'rt-lista' + (d.situacao==='entregue' ? ' entregue' : '');
    lista.innerHTML = evs.map(ev=>'<li><b>'+esc(ev.descricao)+'</b>'
      +(ev.detalhe ? '<small>'+esc(ev.detalhe)+'</small>' : '')
      +'<small>'+esc([dataHoraBR(ev.data), ev.local, ev.destino ? '→ '+ev.destino : ''].filter(Boolean).join(' • '))+'</small></li>').join('');
    info.textContent = (evs.length ? evs.length+' evento(s)' : 'Nenhum evento registrado ainda para este código.')
      + (d.consultado_em ? ' — consultado em '+dataHoraBR(d.consultado_em)+' UTC' : '')
      + (d.cache ? ' (em cache)' : '');
    if(d.aviso){ err.textContent = d.aviso; err.hidden = false; }
    if(d.status_atualizado){ toast('Objeto entregue — status atualizado para "entregue".'); load(); }
  }catch(ex){
    if(window._rtCtx !== ctx) return;
    info.textContent = 'Não foi possível consultar agora. Você pode acompanhar pelo site dos Correios.';
    err.textContent = ex.message; err.hidden = false;
  }finally{ btn.disabled = false; }
}
/* modal de edição: corrige nome, código, WhatsApp, e-mail e observações (com ou sem backend) */
function abrirEdicao(id, e, local){
  window._editCtx = { id: id, local: local };
  $('ed-nome').value = e.destinatario || '';
  $('ed-codigo').value = e.codigo || '';
  $('ed-fone').value = e.celular ? mascararFoneBR(e.celular) : '';
  $('ed-email').value = e.email || '';
  $('ed-desc').value = e.descricao || '';
  const cm = $('ed-codigo-msg'); if(cm){ cm.className='field-msg'; cm.textContent='Formato: 2 letras + 9 números + BR'; }
  const em2 = $('ed-email-msg'); if(em2){ em2.className='field-msg'; em2.textContent='Para enviar notificação por e-mail'; }
  const er = $('ed-err'); if(er){ er.hidden = true; er.textContent=''; }
  $('modal-edit').hidden = false;
  setTimeout(()=>{ const i=$('ed-nome'); if(i) i.focus(); }, 50);
}
async function salvarEdicao(){
  const ctx = window._editCtx; if(!ctx) return;
  const err = $('ed-err');
  const mostraErro = m=>{ if(err){ err.textContent = m; err.hidden = false; } else toast(m); };
  const nome = $('ed-nome').value.trim();
  const codigo = limparCodigo($('ed-codigo').value);
  $('ed-codigo').value = codigo;
  const email = $('ed-email').value.trim();
  const fone = $('ed-fone').value.trim();
  const desc = $('ed-desc').value.trim();
  if(!nome){ mostraErro('Informe o destinatário.'); $('ed-nome').focus(); return; }
  if(!codigo){ mostraErro('Informe o código de rastreio.'); $('ed-codigo').focus(); return; }
  if(!codigoValido(codigo)){ mostraErro('Código inválido. Use 2 letras + 9 números + BR (ex: AA123456789BR).'); $('ed-codigo').focus(); return; }
  if(email){ const erMail = erroEmail(email); if(erMail){ mostraErro('E-mail inválido: '+erMail); $('ed-email').focus(); return; } }
  if(!foneValido(fone)){ mostraErro('WhatsApp inválido — use DDD + 8/9 dígitos, ex: (11) 91234-5678.'); $('ed-fone').focus(); return; }
  if(!email && !fone){ mostraErro('Informe ao menos um contato (e-mail ou WhatsApp).'); return; }
  const outro = state.envios.find(x=>String(x._id)!==String(ctx.id) && String(x.codigo).toUpperCase()===codigo);
  if(outro && !confirm('Este código já está em outro envio ('+outro.destinatario+'). Salvar mesmo assim?')) return;
  const body = {destinatario:nome, codigo:codigo, celular:fone, email:email, descricao:desc};
  if(ctx.local){
    const l = lerLocais(); const it = l.find(x=>String(x._id)===String(ctx.id));
    if(it){ Object.assign(it, body); it.link = linkRastreio(codigo); gravarLocais(l); }
    const st = state.envios.find(x=>String(x._id)===String(ctx.id));
    if(st){ Object.assign(st, body); st.link = linkRastreio(codigo); render(); }
    $('modal-edit').hidden = true;
    toast('Alterações salvas (neste navegador). Sincroniza quando o backend ligar.');
    return;
  }
  try{
    const btnEd = $('btn-ed-salvar');
    if(btnEd) btnEd.disabled = true; /* trava durante o PUT: duplo clique não reenvia */
    await api('/envios/'+ctx.id, {method:'PUT', body:JSON.stringify(body)});
    $('modal-edit').hidden = true;
    toast('Envio atualizado!');
    await load();
  }catch(e){
    if(isNetError(e)){
      /* Envio que veio do BANCO precisa do backend para ser alterado: avisa e mantém o modal aberto.
         (Antes, este caminho criava uma cópia local com o mesmo _id — o card aparecia duplicado,
         o status virava 'pendente' e a cópia era descartada na sincronização.) */
      mostraErro('Sem servidor — não deu para salvar a edição agora. Confira se o backend está no ar (iniciar-sistema.bat) e clique em Salvar de novo.');
    } else mostraErro(e.message);
  }finally{
    const btnEd2 = $('btn-ed-salvar');
    if(btnEd2) btnEd2.disabled = false;
  }
}
/* modal do WhatsApp: mostra a mensagem, copia para a área de transferência e abre o chat */
$('btn-wa-enviar').onclick = async ()=>{
  const ctx = window._waCtx; if(!ctx) return;
  const fone = String(ctx.fone||'').replace(/\D/g,'');
  const copiado = await copiarTexto($('wa-msg').value);
  window.open('https://wa.me/55'+fone,'_blank');
  if(ctx.local){
    const l = lerLocais(); const it = l.find(x=>String(x._id)===String(ctx.id));
    if(it && it.status!=='entregue'){ it.status='a_caminho'; it.notificado=1; gravarLocais(l); }
  } else if(ctx.status!=='entregue'){ await api('/envios/'+ctx.id+'/notificado',{method:'PATCH',body:'{}'}).catch(()=>{}); }
  $('modal-wa').hidden = true;
  toast(copiado ? 'Mensagem copiada! Cole no WhatsApp com Ctrl+V.' : 'Copie a mensagem da janela e cole no WhatsApp.');
  await load();
};
document.getElementById('btn-add').onclick = async ()=>{
  const nome = $('f-nome').value.trim();
  const codigo = limparCodigo($('f-codigo').value);
  $('f-codigo').value = codigo;
  const email = $('f-email').value.trim();
  const fone = $('f-fone').value.trim();
  const desc = $('f-desc').value.trim();
  const status = $('f-status').value;
  if(!nome){ toast('Informe o destinatário.'); $('f-nome').focus(); return; }
  if(!codigo){ toast('Informe o código de rastreio.'); $('f-codigo').focus(); return; }
  if(!codigoValido(codigo)){ mascaraRastreio($('f-codigo')); toast('Código inválido. Use 2 letras + 9 números + BR (ex: AA123456789BR).'); $('f-codigo').focus(); return; }
  if(email){
    const erMail = erroEmail(email);
    if(erMail){ const m=$('f-email-msg'); if(m){ m.className='field-msg err'; m.textContent='✕ '+erMail; } toast('E-mail inválido: '+erMail); $('f-email').focus(); return; }
  }
  if(!foneValido(fone)){ toast('WhatsApp inválido — use DDD + 8/9 dígitos, ex: (11) 91234-5678.'); $('f-fone').focus(); return; }
  if(!email && !fone){ toast('Informe ao menos um contato (e-mail ou WhatsApp).'); return; }
  if(state.envios.some(e=>String(e.codigo).toUpperCase()===codigo)){ if(!confirm('Este código já está cadastrado. Cadastrar mesmo assim?')) return; }
  const salvarLocal = ()=>{
    // modo offline: salva no navegador e sincroniza depois
    const novo = {_id:idLocal(), _local:true, destinatario:nome, codigo, email, celular:fone, descricao:desc, status:status||'pendente', criado_em:agoraLocal(), link:linkRastreio(codigo)};
    const locais = lerLocais(); locais.push(novo); gravarLocais(locais);
    $('f-nome').value=''; $('f-codigo').value=''; $('f-email').value=''; $('f-fone').value=''; $('f-desc').value='';
    const m = $('f-codigo-msg'); if(m){ m.className='field-msg'; m.textContent='Formato: 2 letras + 9 números + BR'; }
    state.envios = [...state.envios, novo]; render();
    toast('Sem servidor — salvo no navegador. Sincroniza sozinho quando o backend ligar.');
  };
  if(state.online !== true){ salvarLocal(); return; } /* online só quando o checkDB confirmou; undefined/false = offline: grava direto, sem tentar a rede */
  const btnAdd = $('btn-add');
  if(btnAdd) btnAdd.disabled = true; /* trava durante o POST: duplo clique não cria registro duplicado */
  try{
    const r = await api('/envios',{method:'POST',body:JSON.stringify({destinatario:nome,codigo,email,celular:fone,descricao:desc,status})});
    $('f-nome').value=''; $('f-codigo').value=''; $('f-email').value=''; $('f-fone').value=''; $('f-desc').value='';
    const m = $('f-codigo-msg'); if(m){ m.className='field-msg'; m.textContent='Formato: 2 letras + 9 números + BR'; }
    toast(r.message || 'Envio cadastrado!');
    await load();
  }catch(err){
    if(isNetError(err)){ salvarLocal(); } else { toast(err.message); }
  }finally{
    if(btnAdd) btnAdd.disabled = false;
  }
};

document.getElementById('btn-do-login').onclick = async ()=>{
  const email=state.adminEmail, senha=$('l-senha').value;
  $('l-err').hidden = true;
  try{
    const d = await api('/auth/login',{method:'POST',body:JSON.stringify({email,senha})});
    state.token = d.token; localStorage.setItem('rf_token', d.token);
    state.usuarioId = (d.user && d.user.id) || null;
    state.admin = !!(d.user && d.user.admin);
    window._loginPedido = false;
    $('modal-login').hidden = true; $('l-senha').value=''; toast('Bem-vindo!');
    await load();
  }catch(e){ $('l-err').textContent = e.message; $('l-err').hidden = false; }
};
/* melhoria v20: logout revoga o token no servidor (antes so apagava local) */
async function fazerLogout(){
  try{ if(state.token) await api('/auth/logout',{method:'POST',body:'{}'}); }catch(e){}
  state.token=''; localStorage.removeItem('rf_token');
  state.usuarioId = null;
  toast('Sessão encerrada.');
  pedirLogin('Você saiu. Entre novamente para continuar.');
  await load();
}
/* melhoria v20: notifica todos os pendentes de uma vez (antes: 1 por 1) */
async function notificarMassa(){
  if(!confirm('Enviar e-mail para TODOS os pendentes com e-mail cadastrado?')) return;
  try{
    const r = await api('/notificacoes/massa',{method:'POST',body:JSON.stringify({canal:'email'})});
    toast(r.message || 'Disparo concluído!');
    await load();
  }catch(e){ toast(e.message); }
}
/* listeners + import: funções declaradas abaixo (hoisting) */
/* melhoria v22: backup do banco (.db) — só aparece e funciona para administrador */
async function baixarBackup(){
  try{
    const r = await fetch(API + '/backup', {headers: headers()});
    if(!r.ok){
      let msg = 'HTTP ' + r.status;
      try{ const d = await r.json(); if(d.detail) msg = d.detail; }catch(e){}
      throw new Error(msg);
    }
    const blob = await r.blob();
    const cd = r.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="?([^";]+)"?/);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : 'backup-rastreio.db';
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 5000);
    toast('Backup baixado.');
  }catch(err){ toast('Backup falhou: ' + err.message); }
}
function boot(){
  /* file:// (arquivo aberto direto no navegador): nada do /static carrega sem servidor e a API é
     inalcançável — avisa uma vez em vez de fingir que está tudo certo */
  if(location.protocol === 'file:'){
    toast('Você abriu o arquivo HTML direto (file://). Para o app funcionar inteiro, abra por http://localhost:8080/ (abrir-servidor-local.bat) ou http://localhost:3000/ (backend).');
  }
  $('f-codigo').addEventListener('input', e=>mascaraRastreio(e.target));
  $('f-fone').addEventListener('input', e=>mascaraFone(e.target));
  $('f-email').addEventListener('input', e=>mascaraEmail(e.target));
  $('f-busca').addEventListener('input', ()=>{
    /* debounce: evita re-render a cada tecla em listas grandes (só renderiza 150ms depois de parar) */
    clearTimeout(window._buscaT);
    window._buscaT = setTimeout(()=>{ _listaExibida = PAGINA_LINHAS; render(); }, 150);
  });
  $('f-filtro').addEventListener('change', ()=>{ _listaExibida = PAGINA_LINHAS; render(); });
  $('btn-login').onclick = ()=>{ $('modal-login').hidden = false; const fix=$('l-email-fix'); if(fix) fix.textContent=state.adminEmail; };
  const btnOut = $('btn-logout'); if(btnOut) btnOut.onclick = fazerLogout;
  const btnMassa = $('btn-notifica-massa'); if(btnMassa) btnMassa.onclick = notificarMassa;
  $('ed-codigo').addEventListener('input', e=>mascaraRastreio(e.target));
  $('ed-fone').addEventListener('input', e=>mascaraFone(e.target));
  $('ed-email').addEventListener('input', e=>mascaraEmail(e.target));
  document.getElementById('btn-ed-salvar').onclick = salvarEdicao;
  $('btn-rt-atualizar').onclick = ()=>consultarRastreio(true);
  $('btn-rt-site').onclick = ()=>{ if(window._rtCtx) window.open(window._rtCtx.link,'_blank'); };
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>{ const ov = b.closest('.modal-ov'); if(ov) ov.hidden = true; });
  document.getElementById('drop').onclick = ()=>document.getElementById('f-file').click();
  document.getElementById('f-file').onchange = e=>{ if(e.target.files[0]) lerArquivo(e.target.files[0]); e.target.value=''; };
  const dd = document.getElementById('drop');
  dd.addEventListener('dragover', e=>{ e.preventDefault(); dd.classList.add('over'); });
  dd.addEventListener('dragleave', ()=>dd.classList.remove('over'));
  dd.addEventListener('drop', e=>{ e.preventDefault(); dd.classList.remove('over'); if(e.dataTransfer.files[0]) lerArquivo(e.dataTransfer.files[0]); });
  document.getElementById('btn-import-txt').onclick = ()=>{ const t=$('f-csv').value.trim(); if(!t){ toast('Cole os dados primeiro.'); return; } importarLinhas(parseCsvLinhas(t)); $('f-csv').value=''; };
  document.getElementById('btn-modelo').onclick = ()=>{
    const a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob(["\ufeffNome,Codigo,Celular,Email,Descricao\nMaria Silva,AA123456789BR,(11) 91234-5678,maria@email.com,Pedido #1024\n",{type:'text/csv'}]));
    a.download='modelo-importacao.csv'; a.click();
  };
  document.getElementById('btn-exp-csv').onclick = exportarCSV;
  document.getElementById('btn-exp-xlsx').onclick = exportarXLSX;
  $('btn-backup').onclick = baixarBackup;
  /* melhoria v22: clique nos cards de estatística filtra a lista (mantém select e cards em sincronia) */
  document.querySelectorAll('.stat[data-filtro]').forEach(c=>{
    c.onclick = ()=>{ $('f-filtro').value = c.dataset.filtro; _listaExibida = PAGINA_LINHAS; render(); };
  });
  /* v29: "Carregar mais" — renderiza mais linhas da lista (evita o innerHTML gigante) */
  const btnMais = $('btn-mais');
  if(btnMais) btnMais.onclick = ()=>{ _listaExibida += PAGINA_LINHAS; render(); };
}
/* ===== importação Excel/CSV (lógica do sistema antigo) ===== */
function semAcento(s){ return String(s||'').toLowerCase().normalize('NFD').replace(/[^a-z0-9 ]/gi,' '); }
function parseCsvLinhas(texto){
  const linhas = []; let linha = [], campo = '', emAspas = false;
  for(let i=0;i<texto.length;i++){
    const c = texto[i];
    if(emAspas){ if(c==='"' && texto[i+1]==='"'){ campo+='"'; i++; } else if(c==='"') emAspas=false; else campo+=c; }
    else if(c==='"') emAspas = true;
    else if(c===','||c===';'||c==='\t'){ linha.push(campo.trim()); campo=''; }
    else if(c==='\n'||c==='\r'){ if(c==='\r'&&texto[i+1]==='\n') i++; linha.push(campo.trim()); campo=''; if(linha.some(v=>v)) linhas.push(linha); linha=[]; }
    else campo += c;
  }
  linha.push(campo.trim()); if(linha.some(v=>v)) linhas.push(linha);
  return linhas;
}
function validarLinha(nome, codigo, cel, email){
  codigo = limparCodigo(codigo);
  email = String(email||'').trim();
  if(!nome || !codigo) return {ok:false, motivo:'nome ou código vazio'};
  if(!codigoValido(codigo)) return {ok:false, motivo:'código fora do padrão AA123456789BR'};
  if(String(cel||'').trim() && !foneValido(cel)) return {ok:false, motivo:'celular inválido (DDD + 8/9 dígitos)'};
  if(email){
    const er = erroEmail(email);
    if(er) return {ok:false, motivo:'e-mail inválido — '+er};
  }
  return {ok:true, codigo, email};
}
async function importarLinhas(dados){
  if(!Array.isArray(dados) || !dados.length){ toast('Nada para importar.'); return; }
  const linhas = dados.map(l=>Array.isArray(l)?l.map(v=>String(v??'').trim()):[]).filter(l=>l.some(v=>v!==''));
  if(!linhas.length){ toast('Planilha vazia.'); return; }
  const ehCab = l => l.some(c=>/nome|destinat|cliente|codigo|rastre|objeto|celular|telefone|whats|email|descri|conteudo|obs|status|situac/i.test(semAcento(c)));
  let iN=0,iC=1,iT=2,iE=3,iD=4,iS=5,inicio=0;
  if(ehCab(linhas[0])){ inicio=1; linhas[0].forEach((c,i)=>{ const n=semAcento(c);
    if(/destinat|nome|cliente/.test(n)) iN=i; else if(/codigo|rastre|objeto/.test(n)) iC=i;
    else if(/celular|telefone|whats|fone|cel/.test(n)) iT=i; else if(/email|mail/.test(n)) iE=i;
    else if(/descri|conteudo|obs|produto|item/.test(n)) iD=i; else if(/status|situac/.test(n)) iS=i; }); }
  const bons=[], atualiza=[], motivos={}; let ignor=0;
  for(let k=inicio;k<linhas.length;k++){
    const L=linhas[k];
    const v = validarLinha(L[iN]||'', L[iC]||'', L[iT]||'', L[iE]||'');
    if(!v.ok){ ignor++; motivos[v.motivo]=(motivos[v.motivo]||0)+1; continue; }
    let st = String(L[iS]||'').trim().toLowerCase();
    if(st!=='pendente'&&st!=='a_caminho'&&st!=='entregue') st='pendente';
    const dados={destinatario:String(L[iN]).trim(), codigo:v.codigo, celular:String(L[iT]||'').trim(), email:v.email, descricao:String(L[iD]||'').trim(), status:st};
    const ex = state.envios.find(e=>String(e.codigo).toUpperCase()===v.codigo);
    if(ex){ atualiza.push({ex, dados}); continue; }
    if(bons.some(b=>b.codigo===v.codigo)){ ignor++; motivos['código duplicado na planilha']=(motivos['código duplicado na planilha']||0)+1; continue; }
    bons.push(dados);
  }
  const msg = $('import-msg');
  if(!bons.length && !atualiza.length){ const d=Object.entries(motivos).map(([k,v])=>v+'x '+k).join('; '); if(msg) msg.textContent='Nenhuma linha válida: '+d; toast('Nenhuma linha válida ('+ignor+' ignoradas).'); return; }
  const resumo = Object.entries(motivos).map(([k,v])=>v+'x '+k).join('; ');
  const aplicaStatusLocal = (updEx, updSt)=>{
    // caminho online p/ item _local: leitura+escrita única por item (chamadas sequenciais, sem snapshot obsoleto)
    updEx.status = updSt;
    const l = lerLocais();
    const it = l.find(x=>String(x.codigo).toUpperCase()===String(updEx.codigo).toUpperCase());
    if(it){ it.status = updSt; it.notificado = updSt==='pendente' ? 0 : 1; gravarLocais(l); }
    else if(updEx._local){
      const l2 = lerLocais(); l2.push(updEx); gravarLocais(l2);
    }
  };
  const salvarLocal = ()=>{
    // modo offline: UMA única leitura/escrita no localStorage.
    // (Ler de novo dentro do loop e gravar o snapshot antigo depois apagava as atualizações de status.)
    const locais = lerLocais();
    const porCodigo = new Map(locais.map(o=>[String(o.codigo||'').toUpperCase(), o]));
    let nUpd = 0;
    atualiza.forEach(({ex, dados})=>{
      ex.status = dados.status; // reflete na tela
      const it = porCodigo.get(String(dados.codigo).toUpperCase());
      if(it){ it.status = dados.status; it.notificado = dados.status==='pendente' ? 0 : 1; nUpd++; }
      else{
        // visível mas fora do storage (ex.: veio do banco antes de cair): copia local p/ não perder
        const copia = {_id: (ex && ex._id!=null ? ex._id : idLocal()-Math.floor(Math.random()*100000)), _local:true, destinatario:dados.destinatario, codigo:dados.codigo, email:dados.email||'', celular:dados.celular||'', descricao:dados.descricao||'', status:dados.status, notificado:dados.status==='pendente'?0:1, criado_em:(ex&&ex.criado_em)||agoraLocal(), link:linkRastreio(dados.codigo)};
        locais.push(copia); porCodigo.set(String(dados.codigo).toUpperCase(), copia); nUpd++;
      }
    });
    const novos = bons.filter(b=>!porCodigo.get(String(b.codigo).toUpperCase())).map(b=>({_id:idLocal()-Math.floor(Math.random()*100000), _local:true, destinatario:b.destinatario, codigo:b.codigo, email:b.email||'', celular:b.celular||'', descricao:b.descricao||'', status:b.status||'pendente', notificado:(b.status||'pendente')==='pendente'?0:1, criado_em:agoraLocal(), link:linkRastreio(b.codigo)}));
    novos.forEach(n2=>{ locais.push(n2); porCodigo.set(String(n2.codigo).toUpperCase(), n2); });
    gravarLocais(locais);
    state.envios = [...state.envios, ...novos]; render();
    const partes = [];
    if(novos.length) partes.push(novos.length+' novo(s)');
    if(nUpd) partes.push(nUpd+' status atualizado(s)');
    const txt = (partes.join(' + ')||'nada novo')+' salvo(s) neste navegador (sem servidor)'+(ignor?' — '+ignor+' ignorado(s): '+resumo:'')+'. Sincronizam sozinhos quando o backend ligar.';
    if(msg) msg.textContent = txt;
    toast('Sem servidor — '+(partes.join(' + ')||'nada novo')+'. Sincroniza quando o backend ligar.');
  };
  if(state.online !== true){ salvarLocal(); return; } /* online só quando o checkDB confirmou; undefined/false = offline: grava direto, sem tentar a rede */
  try{
    let msgUpd = '';
    if(atualiza.length){
      let nOk = 0;
      for(const {ex, dados} of atualiza){
        try{
          if(ex._local){ aplicaStatusLocal(ex, dados.status); nOk++; }
          else { await api('/envios/'+ex._id,{method:'PUT',body:JSON.stringify({status:dados.status})}); nOk++; }
        }catch(e2){ /* mantém o resto */ }
      }
      if(nOk) msgUpd = ' + '+nOk+' status atualizado(s)';
      await load();
    }
    if(!bons.length){ if(msg) msg.textContent = msgUpd.replace(/^ \+ /,'')+(ignor?' — '+ignor+' ignorado(s): '+resumo:''); toast(msgUpd.replace(/^ \+ /,'')||'Nada novo para importar.'); return; }
    const r = await api('/envios',{method:'POST',body:JSON.stringify({envios:bons})});
    const n = (r.envios||[]).length || bons.length;
    const srv = (r.erros||[]).length ? ' | servidor: '+r.erros.slice(0,4).join('; ') : '';
    if(msg) msg.textContent = n+' importado(s)'+msgUpd+(ignor?' — '+ignor+' ignorado(s): '+resumo:'')+srv;
    toast(r.message || (n+' envio(s) importado(s)!'+msgUpd));
    await load();
  }catch(e){
    if(isNetError(e)){ salvarLocal(); }
    else { const msg2=$('import-msg'); if(msg2) msg2.textContent=e.message; toast(e.message); }
  }
}
async function lerArquivo(file){
  if(!file) return;
  const ext = (file.name.split('.').pop()||'').toLowerCase();
  toast('Lendo '+file.name+'...');
  try{
    if(ext==='csv'){ importarLinhas(parseCsvLinhas(await file.text())); }
    else if(ext==='xlsx'||ext==='xls'){
      const XLSX = await carregarXLSX();   /* v29: baixa a lib (861 KB) só agora, sob demanda */
      const wb = XLSX.read(await file.arrayBuffer(), {type:'array'});
      const sh = wb.Sheets[wb.SheetNames[0]];
      importarLinhas(XLSX.utils.sheet_to_json(sh,{header:1,defval:'',raw:false}));
    }
    else toast('Formato não suportado. Use .csv, .xlsx ou .xls');
  }catch(e){ toast('Erro ao ler arquivo: '+e.message); }
}
function exportarCSV(){
  const lista = filtrados().lista; /* exporta o recorte da tela (filtro/busca ativos) */
  if(!lista.length){ toast('Nada para exportar (verifique o filtro/busca).'); return; }
  const q2 = v => '"'+String(v??'').replace(/"/g,'""')+'"';
  const csv = ['Nome,Codigo,Celular,Email,Descricao,Status'];
  lista.forEach(e=>csv.push([e.destinatario,e.codigo,e.celular,e.email||'',e.descricao||'',uiStatus(e)].map(q2).join(',')));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(["\ufeff"+csv.join('\n'),{type:'text/csv;charset=utf-8'}]));
  a.download = 'envios.csv'; a.click();
}
boot();
load();
/* reconexão: o proprio checkDB() reagenda com backoff (5s→60s); este intervalo
   e so rede de seguranca caso algum timer seja limpo — nao martela o servidor */
setInterval(()=>{ if(state.online === false && !window._retryT) load(); }, 60000);
window.addEventListener('online', ()=>{ if(!state.online) load(); });
/* atualização automática: se o servidor tiver versão nova, recarrega a página sozinho (fim das abas velhas travadas) */
async function checarVersao(){
  if(state.online === false) return; /* backend fora do ar: load() ja tenta reconectar a cada 60s — sem isso o console enche de ERR_CONNECTION_REFUSED */
  try{
    const r = await fetch(API+'/versao', {cache:'no-store'});
    const d = await r.json();
    if(d && d.versao && String(d.versao) !== APP_V){
      toast('Atualizando para a versão mais nova...');
      setTimeout(()=>location.reload(), 600);
    }
  }catch(e){}
}
setTimeout(checarVersao, 5000);
setInterval(checarVersao, 15000);
/* ===== validação / máscaras (trazidas do sistema antigo) ===== */
async function exportarXLSX(){
  const lista = filtrados().lista; /* exporta o recorte da tela (filtro/busca ativos) */
  if(!lista.length){ toast('Nada para exportar (verifique o filtro/busca).'); return; }
  let XLSX;
  try{
    toast('Preparando o Excel...');
    XLSX = await carregarXLSX();   /* v29: baixa a lib (861 KB) só agora, sob demanda */
  }catch(e){ toast(e.message); return; }
  const ws = XLSX.utils.json_to_sheet(lista.map(e=>({Nome:e.destinatario,Codigo:e.codigo,Celular:e.celular,Email:e.email,Descricao:e.descricao,Status:uiStatus(e)})));
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Envios');
  XLSX.writeFile(wb, 'envios.xlsx');
}
/* ===== Excel (SheetJS) carregado SOB DEMANDA =====
   v29: a lib xlsx.full.min.js tem 861 KB (92% do peso do site). Antes ela era um
   <script> bloqueante no index.html: TODO visitante baixava e parseava 861 KB
   mesmo sem nunca tocar em "Exportar Excel". Agora ela só é baixada no momento
   em que o usuário realmente precisa (exportar .xlsx ou importar .xlsx).
   O payload inicial caiu de 935 KB para 74 KB (-93%). */
let _xlsxPromise = null;
function carregarXLSX(){
  if(typeof XLSX !== 'undefined') return Promise.resolve(XLSX);
  if(_xlsxPromise) return _xlsxPromise;            /* já está baixando: não duplica */
  _xlsxPromise = new Promise((resolve, reject)=>{
    const s = document.createElement('script');
    s.src = '/static/libs/xlsx.full.min.js?v=' + APP_V;
    s.async = true;
    s.onload = ()=>{
      if(typeof XLSX !== 'undefined') resolve(XLSX);
      else reject(new Error('Biblioteca Excel não carregou (Ctrl+F5 para recarregar).'));
    };
    s.onerror = ()=>{ _xlsxPromise = null; reject(new Error('Falha ao baixar a biblioteca Excel (sem internet?).')); };
    document.head.appendChild(s);
  });
  return _xlsxPromise;
}
/* ===== máscaras de input ===== */
function mascaraRastreio(input){
  input.value = limparCodigo(input.value);
  /* msg do modal certo: ed-codigo alimenta ed-codigo-msg (antes sempre atualizava
     f-codigo-msg do formulário de criação, escondido atrás do modal) */
  const pre = (input.id === 'ed-codigo') ? 'ed' : 'f';
  const msg = $(pre+'-codigo-msg');
  const {txt, cls} = codigoMsg(input.value);
  input.classList.toggle('invalid', input.value.length===13 && !codigoValido(input.value));
  if(msg){ msg.className = cls; msg.textContent = txt; }
}
function mascaraEmail(input){
  const pre = (input.id === 'ed-email') ? 'ed' : 'f';
  const m = $(pre+'-email-msg'); if(!m) return;
  if(!input.value.trim()){ m.className='field-msg'; m.textContent='Para enviar notificação por e-mail'; return; }
  const er = erroEmail(input.value);
  if(er){ m.className='field-msg err'; m.textContent='✕ '+er; }
  else { m.className='field-msg ok'; m.textContent='✓ E-mail válido'; }
}
function mascaraFone(input){
  let v = input.value.replace(/\D/g,'');
  if(v.startsWith('0055')) v = '55' + v.slice(4);
  if(v.startsWith('0')) v = v.slice(1);
  if(v.startsWith('55') && (v.length===12||v.length===13)) v = v.slice(2);
  v = v.slice(0,11);
  if(v.length === 11) input.value = '('+v.slice(0,2)+') '+v.slice(2,7)+'-'+v.slice(7);
  else if(v.length === 10) input.value = '('+v.slice(0,2)+') '+v.slice(2,6)+'-'+v.slice(6);
  else if(v.length > 2) input.value = '('+v.slice(0,2)+') '+v.slice(2);
  else if(v.length > 0) input.value = '('+v;
}
function mascararFoneBR(digitos){
  const v = String(digitos||'').replace(/\D/g,'');
  if(v.length === 11) return '('+v.slice(0,2)+') '+v.slice(2,7)+'-'+v.slice(7);
  if(v.length === 10) return '('+v.slice(0,2)+') '+v.slice(2,6)+'-'+v.slice(6);
  return String(digitos||'');
}
