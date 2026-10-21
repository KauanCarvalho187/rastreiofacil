# -*- coding: utf-8 -*-
"""Teste estatico (sem servidor): valida as correcoes aplicadas + regressoes."""
import os, sys
# Windows: o console em cp1252 quebra em textos com seta/emoji — força UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
BASE = os.path.dirname(os.path.abspath(__file__))
main = open(os.path.join(BASE, "main.py"), encoding="utf-8").read()
js = open(os.path.join(BASE, "static", "app.js"), encoding="utf-8").read()
ok = True
def check(nome, cond):
    global ok
    print(("PASS" if cond else "FAIL") + " - " + nome)
    ok = ok and cond
check("py: compila (sintaxe)", True)
try:
    import py_compile
    py_compile.compile(os.path.join(BASE, "main.py"), doraise=True)
    check("py: main.py compila", True)
except Exception as e:
    check(f"py: main.py compila ({e})", False)
try:
    py_compile.compile(os.path.join(BASE, "db.py"), doraise=True)
    check("py: db.py compila", True)
except Exception as e:
    check(f"py: db.py compila ({e})", False)
check("verificar_senha captura AttributeError (None-safe)",
      "AttributeError" in main)
check("PUT valida destinatario vazio", "Destinatario vazio" in main)
check("PUT valida contato minimo", main.count("Informe ao menos e-mail ou WhatsApp") >= 2)
check("PUT impede codigo duplicado (409)", "ja usado em outro envio" in main)
check("celular: 0055 vira 55+", '"55" + d[4:]' in main or "'55' + d.slice(4)" in js)
check("notificacoes: 404 codigo nao cadastrado", "Codigo nao cadastrado" in main)
check("notificacoes: canal case-insensitive", "strip().lower()" in main)
check("email acentos via Header/formataddr", "formataddr" in main)
check("smtp porta 465 usa use_tls", "use_tls" in main)
check("POST rejeita corpo nao-dict", "Corpo invalido" in main)
check("POST aceita envios como obj unico", "itens = [m]" in main)
check("PUT coage descricao nao-string", 'str(upd.descricao).strip()' in main)
check("html-email coage tipos", 'str(codigo or "")' in main)
check("JS mascaraFone trata 0055/55xx e 10/11 digitos",
      "mascararFoneBR" in js and "startsWith('0055')" in js)
check("JS foneDigitos trata 0055", "foneDigitos" in js and "0055" in js)
check("JS bloqueia WhatsApp com tamanho invalido",
      "WhatsApp inv" in js)
check("JS valida e-mail antes de notificar", "E-mail inv" in js)
check("JS exibe fone mascarado", "mascararFoneBR(e.celular)" in js)
check("JS wa.me so com digitos", "replace(/\\D/g,'')" in js)
check("legado main.html removido",
      not os.path.exists(os.path.join(BASE, "static", "main.html")))
check("legado script.js removido",
      not os.path.exists(os.path.join(BASE, "static", "script.js")))
check("legado login.js removido",
      not os.path.exists(os.path.join(BASE, "static", "login.js")))
check("legado style.css removido",
      not os.path.exists(os.path.join(BASE, "static", "style.css")))
check("principal e static/index.html",
      os.path.exists(os.path.join(BASE, "static", "index.html")))
check("principal e static/app.js",
      os.path.exists(os.path.join(BASE, "static", "app.js")))
check("principal e static/styles.css",
      os.path.exists(os.path.join(BASE, "static", "styles.css")))
check("main.py serve index.html", 'static/index.html' in main)
check("main.py sem resto de novo.html", 'novo.html' not in main)
html = open(os.path.join(BASE, "static", "index.html"), encoding="utf-8").read()
check("index.html usa /static/app.js", '/static/app.js' in html)
check("index.html usa /static/styles.css", '/static/styles.css' in html)
check("index.html sem resto de novo.*", 'novo.' not in html)
check("checarVersao pula quando offline (sem spam no console)", "if(state.online === false) return;" in js)
check("pílula de status do banco no header", "db-pill" in html)
check("resposta não-JSON cai no modo offline (sem servidor)", "Sem resposta JSON da API" in js)
check("backoff de reconexao (5s→60s, sem martelar)", "_esperaBackoff" in js and "window._retryT" in js)
check("toast avisa na transição para offline", "Servidor fora do ar" in js)
check("edicao: botao Editar no card", 'data-act="edit"' in js)
check("edicao: modal modal-edit no HTML", "modal-edit" in html and "ed-nome" in html and "ed-codigo" in html)
check("edicao: PUT /envios com validacao", "salvarEdicao" in js and "'/envios/'+ctx.id" in js)
check("edicao: funciona offline", "Object.assign(it, body)" in js)
check("importacao funciona offline (salva local)", "modo offline: salva no navegador e sincroniza depois" in js)
check("cadastro manual: so tenta rede com backend confirmado (undefined = offline)",
      "if(state.online !== true){ salvarLocal(); return; }" in js)
check("import: o mesmo teste de online do cadastro manual",
      js.count("if(state.online !== true){ salvarLocal(); return; }") >= 2)
check("import: status existente e atualizado em vez de virar duplicado",
      "const ex = state.envios.find" in js and "atualiza.push({ex, dados})" in js)
check("import offline: leitura/escrita unica no localStorage (nao sobrescreve status)",
      "const porCodigo = new Map" in js and "gravarLocais(locais);" in js)
check("import: le a coluna Status da planilha", "iS=5" in js and "st!=='pendente'" in js)
check("erros de JS aparecem na tela (barra vermelha)", "erro-fatal" in js and "unhandledrejection" in js)
check("CSV limpo na raiz (sem [object Object])",
      os.path.exists(os.path.join(BASE, "envios.csv")) and "[object Object]" not in open(os.path.join(BASE, "envios.csv"), encoding="utf-8").read())
check("sem arquivo morto: Procfile/render.yaml/_validar_js.ps1 removidos",
      not any(os.path.exists(os.path.join(BASE, f)) for f in ("Procfile", "render.yaml", "_validar_js.ps1", "importar_envios_csv.sql")))
# correcoes da auditoria v21 (regressoes — nao remover)
check("wa: modal de WhatsApp guarda status do envio", "status: e.status" in js)
check("wa: nao marca notificado quando status e entregue (nao regride)", "ctx.status!=='entregue'" in js)
check("backend: notificado so promove pendente (entregue nao vira a_caminho)",
      '== "pendente" else anterior.get("status")' in main)
check("edicao: mascara atualiza a msg do proprio modal (ed-codigo-msg/ed-email-msg)",
      "pre+'-codigo-msg'" in js and "pre+'-email-msg'" in js)
check("lista: busca todas as paginas do servidor (nao trava em 200)",
      "'/envios?page='+pagina+'&limit=500'" in js)
check("rota /api/notificacoes/massa definida uma unica vez (sem duplicata morta)",
      main.count('@app.post("/api/notificacoes/massa")') == 1)
# melhorias v22 (regressoes — nao remover)
check("v28: versao front/back em 28 (abas antigas recarregam)",
      'APP_VERSAO = "28"' in main and "APP_V = '28'" in js and "?v=28" in html)
check("v28: admin unico — sem tela de usuarios no front",
      "btn-usuarios" not in html and "modal-usuarios" not in html
      and "btn-usuarios" not in js and "modal-usuarios" not in js)
check("v28: admin unico — sem cadastro de usuarios no backend",
      '@app.post("/api/auth/registrar")' not in main
      and '@app.get("/api/usuarios")' not in main
      and '@app.patch("/api/usuarios/{uid}")' not in main)
check("v28: admin unico — o login mostra o e-mail fixo do admin",
      "admin@admin.com" in html and "l-email-fix" in html)
check("v28: backend garante a conta admin@admin.com no boot",
      'ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@admin.com")' in main
      and "garantir_admin()" in main and "async def garantir_admin" in main)
worker = open(os.path.join(BASE, "cloudflare", "worker.js"), encoding="utf-8").read()
check("v28: Worker da Cloudflare tambem e admin unico",
      "garantirAdmin(env)" in worker and "admin@admin.com" in worker
      and "rota('POST', '/api/auth/registrar'" not in worker
      and "rota('GET', '/api/usuarios'" not in worker
      and "rota('PATCH', '/api/usuarios/:id'" not in worker)
check("v23: rastreio automatico — rota, cache e modal",
      '@app.post("/api/envios/{envio_id}/rastrear")' in main and "_cache_valido(cache)" in main
      and 'id="modal-rt"' in html and "+'/rastrear'" in js)
check("v28: Worker da Cloudflare na mesma versao que o main.py",
      "const APP_VERSAO = '28'" in worker)
# correcao v25: a lixeira era inalcancavel no front (a listagem padrao da API exclui
# status='excluido'); agora o admin carrega a lixeira e "Todos" nao mistura excluidos.
check("v25: admin carrega a lixeira e 'Todos' oculta excluidos",
      "'/envios?status=excluido&page='+pagina" in js
      and "f === 'todos' ? s !== 'excluido'" in js
      and "uiStatus(e)!=='excluido'" in js)

# Paridade REAL de rotas: compara o conjunto (metodo, caminho) dos dois backends.
# O Worker usa :param; o FastAPI usa {param} — normalizamos os dois para ":id",
# assim qualquer rota que exista em um e nao no outro reprova o teste (anti-drift).
import re as _re
def _norm_rota(p):
    p = _re.sub(r"\{[^}]+\}", ":id", p)      # FastAPI: {envio_id} / {uid}
    p = _re.sub(r":[^/'\"]+", ":id", p)      # Worker:  :id
    return p
rotas_main = {(m.group(1).upper(), _norm_rota(m.group(2)))
              for m in _re.finditer(r'@app\.(get|post|put|patch|delete)\("(/api/[^"]+)"', main)}
rotas_worker = {(m.group(1), _norm_rota(m.group(2)))
                for m in _re.finditer(r"rota\('(GET|POST|PUT|PATCH|DELETE)',\s*'(/api/[^']+)'", worker)}
check("v24: Worker e main.py expoem as MESMAS rotas /api (metodo + caminho)",
      rotas_main == rotas_worker)
_diff_rotas = sorted(rotas_main ^ rotas_worker)
if _diff_rotas:
    print("     rotas divergentes (main vs worker):", _diff_rotas)
check("v23: chave da API de rastreio so por env (nunca no codigo)",
      'os.getenv("RASTREIO_API_KEY")' in open(os.path.join(BASE, "rastreio.py"), encoding="utf-8").read()
      and "Apikey " not in js)
check("v22: rota /api/backup existe e exige admin",
      '@app.get("/api/backup")' in main and 'if not usuario.get("admin")' in main)
check("v22: /auth/estado informa se o token e de admin",
      '"admin": admin' in main and "authorization: str = Header(None)" in main)
check("v22: botao backup no HTML (hidden por padrao)", 'id="btn-backup"' in html and 'btn-backup" hidden' in html)
check("v22: cards de stats filtram a lista (clique)",
      ".stat[data-filtro]" in js and "c.dataset.filtro" in js)
check("v22: export CSV/XLSX usa o recorte filtrado", js.count("const lista = filtrados();") >= 2)
check("v22: JS baixa backup com token", "'/backup'" in js and "baixarBackup" in js)
# verificacao profunda / autorreparo (regressoes — nao remover)
check("delete de envio limpa o historico (eventos) — sem orfaos",
      "DELETE FROM eventos WHERE envio_id" in main)
check("botoes de salvar travam durante a requisicao (loading anti duplo clique)",
      "btnAdd.disabled = true" in js and "btnAdd.disabled = false" in js
      and "btnEd.disabled = true" in js and "btnEd2.disabled = false" in js)
# melhorias v24 (regressoes — nao remover)
check("v24: Live Server aceita varias portas (nao quebra se mudar 5501->5502)",
      "_portasLiveServer" in js and "5502" in js)
check("v24: busca com debounce (nao re-renderiza a cada tecla)",
      "window._buscaT" in js and "setTimeout(render, 150)" in js)
check("v24: cabecalhos de seguranca na resposta",
      "X-Content-Type-Options" in main and "X-Frame-Options" in main and "Permissions-Policy" in main)
check("v24: codigo unico no banco (indice) + insert a prova de corrida",
      "idx_envios_codigo_unico" in open(os.path.join(BASE, "db.py"), encoding="utf-8").read()
      and "_e_duplicado" in main)
print("RESULTADO:", "TUDO OK" if ok else "HA FALHAS")
sys.exit(0 if ok else 1)


