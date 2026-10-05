# -*- coding: utf-8 -*-
"""Teste estatico (sem servidor): valida as correcoes aplicadas + regressoes."""
import os, sys
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
check("registro exige nome", "Nome obrigatorio" in main)
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
check("pagina de resgate existe e e independente do app.js",
      os.path.exists(os.path.join(BASE, "static", "resgate.html")))
resg = open(os.path.join(BASE, "static", "resgate.html"), encoding="utf-8").read()
check("resgate: nao carrega app.js (funciona sozinho)",
      "src=\"/static/app.js\"" not in resg and "src='app.js'" not in resg
      and "<script src" not in resg)
check("resgate: tem Analisar / Salvar / Reler", all(x in resg for x in ("analisar()", "salvar()", "reler()")))
check("resgate: aceita status com acento (A caminho)", "caminh" in resg)
check("resgate: LimparCodigo completo (nao truncado)",
      "else if(i>=2 && i<11 && /\\d/.test(c)) out+=c; }" in resg and "return out;\n}" in resg)
check("CSV limpo na raiz (sem [object Object])",
      os.path.exists(os.path.join(BASE, "envios.csv")) and "[object Object]" not in open(os.path.join(BASE, "envios.csv"), encoding="utf-8").read())
check("atalho de resgate existe", os.path.exists(os.path.join(BASE, "abrir-resgate.bat")))
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
print("RESULTADO:", "TUDO OK" if ok else "HA FALHAS")
sys.exit(0 if ok else 1)


